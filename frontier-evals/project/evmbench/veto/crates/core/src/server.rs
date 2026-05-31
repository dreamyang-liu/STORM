use crate::errors::ProxyError;
use crate::jsonrpc::{JsonRpcError, JsonRpcPayload, error_response, parse_json_rpc};
use axum::Router;
use axum::body::Body;
use axum::extract::State;
use axum::http::{HeaderMap, Request, StatusCode, Uri};
use axum::response::Response;
use axum::routing::any;
use http_body_util::BodyExt;
use hyper_util::client::legacy::Client;
use hyper_util::client::legacy::connect::HttpConnector;
use hyper_util::rt::TokioExecutor;
use serde_json::{Value, json};
use std::collections::HashSet;
use std::net::SocketAddr;
use std::sync::Arc;
use tracing::{debug, error, warn};
use veto_config::Config;

/// State shared across all request handlers.
#[derive(Debug, Clone)]
pub struct AppState {
    bind_address: SocketAddr,
    upstream: Uri,
    blocked_methods: Arc<HashSet<String>>,
    client: Client<HttpConnector, Body>,
}

impl AppState {
    /// Create a new [`AppState`] from the resolved [`Config`].
    pub fn try_from_config(config: Config) -> Result<Self, ProxyError> {
        let mut connector = HttpConnector::new();
        connector.enforce_http(false);
        let client = Client::builder(TokioExecutor::new()).build(connector);

        let bind_address = config.bind_address();
        let upstream = config.upstream_url().clone();
        let blocked_methods = Arc::new(config.blocked_methods().clone());

        debug!(
            %bind_address,
            upstream = %config.upstream_url(),
            blocked_methods = blocked_methods.len(),
            "initializing app state"
        );

        Ok(Self {
            bind_address,
            upstream,
            blocked_methods,
            client,
        })
    }

    /// Socket address bound by the proxy.
    pub const fn bind_address(&self) -> SocketAddr {
        self.bind_address
    }
}

/// Constructs a new Axum [`Router`] with the provided application state.
pub fn router(state: AppState) -> Router {
    Router::new().fallback(any(proxy_handler)).with_state(state)
}

async fn proxy_handler(State(state): State<AppState>, req: Request<Body>) -> Response {
    match process_request(&state, req).await {
        Ok(response) => response,
        Err(HandlerError::JsonRpc(response)) => response,
        Err(HandlerError::Internal(error)) => {
            error!(error = ?error, "proxy handler failed");
            Response::builder()
                .status(StatusCode::INTERNAL_SERVER_ERROR)
                .body(Body::from("internal server error"))
                .expect("valid response")
        }
    }
}

/// Validate the JSON-RPC payload, blocking or forwarding it upstream as needed.
async fn process_request(state: &AppState, req: Request<Body>) -> Result<Response, HandlerError> {
    let (parts, body) = req.into_parts();
    let collected = body.collect().await.map_err(|error| {
        error!(error = ?error, "failed to read request body");
        HandlerError::from(ProxyError::Body(Box::new(error)))
    })?;
    let bytes = collected.to_bytes();

    let json_rpc = match parse_json_rpc(&bytes) {
        Ok(request) => request,
        Err(error) => {
            debug!(error = ?error, "rejecting json-rpc payload");
            return Err(HandlerError::from(error));
        }
    };
    // Reject any request (including batched) that contains a blocked method.
    let is_blocked = |method: &str| state.blocked_methods.contains(&method.to_ascii_lowercase());
    match &json_rpc {
        JsonRpcPayload::Single(request) => {
            debug!(method = %request.method, "received json-rpc request");
            if is_blocked(&request.method) {
                warn!(method = %request.method, "blocked json-rpc method");
                let error_payload = blocked_method_response(&request.id, &request.method);
                return Ok(error_payload);
            }
        }
        JsonRpcPayload::Batch(requests) => {
            let blocked: Vec<&str> = requests
                .iter()
                .filter(|r| is_blocked(&r.method))
                .map(|r| r.method.as_str())
                .collect();
            debug!(batch_len = requests.len(), "received json-rpc batch");
            if !blocked.is_empty() {
                warn!(blocked = ?blocked, "blocked json-rpc batch due to blocked method(s)");
                // Deny the whole batch deterministically (avoid allowing mixed probe batches).
                let payload = json!({
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32601,
                        "message": "Batch request blocked by veto proxy",
                    },
                    "id": Value::Null,
                });
                return Ok(Response::builder()
                    .status(StatusCode::OK)
                    .header("content-type", "application/json")
                    .body(Body::from(payload.to_string()))
                    .expect("valid blocked response"));
            }
        }
    }

    let target_uri = match build_target_uri(&state.upstream, &parts.uri) {
        Ok(uri) => uri,
        Err(error) => {
            error!(
                error = ?error,
                incoming = %parts.uri,
                upstream = %state.upstream,
                "failed to construct upstream uri"
            );
            return Err(HandlerError::from(error));
        }
    };

    debug!(upstream = %target_uri, "forwarding json-rpc request");

    let mut forward_parts = parts;
    forward_parts.uri = target_uri.clone();

    let mut forward_request = Request::from_parts(forward_parts, Body::from(bytes));
    sanitize_request_headers(forward_request.headers_mut());

    let response = state
        .client
        .request(forward_request)
        .await
        .map_err(|error| {
            let method = match &json_rpc {
                JsonRpcPayload::Single(req) => req.method.as_str(),
                JsonRpcPayload::Batch(_) => "<batch>",
            };
            error!(
                error = ?error,
                method = %method,
                upstream = %target_uri,
                "upstream request failed"
            );
            HandlerError::from(ProxyError::Upstream(error))
        })?
        .map(Body::new);

    Ok(response)
}

/// Remove hop-by-hop headers before forwarding the request upstream.
fn sanitize_request_headers(headers: &mut HeaderMap) {
    headers.remove("host");
}

/// Build the JSON-RPC error [`Response`] sent when a method is blocked.
fn blocked_method_response(id: &Value, method: &str) -> Response {
    let payload = json!({
        "jsonrpc": "2.0",
        "error": {
            "code": -32601,
            "message": format!("Method '{method}' blocked by veto proxy"),
        },
        "id": id.clone(),
    });

    Response::builder()
        .status(StatusCode::OK)
        .header("content-type", "application/json")
        .body(Body::from(payload.to_string()))
        .expect("valid blocked response")
}

/// Construct the upstream [`Uri`] by combining the base host with the incoming path/query.
fn build_target_uri(base: &Uri, incoming: &Uri) -> Result<Uri, ProxyError> {
    let mut parts = base.clone().into_parts();
    if let Some(path_and_query) = incoming.path_and_query() {
        parts.path_and_query = Some(path_and_query.clone());
    }
    Uri::from_parts(parts).map_err(ProxyError::BadUpstreamUri)
}

#[derive(Debug)]
enum HandlerError {
    JsonRpc(Response),
    Internal(ProxyError),
}

impl From<ProxyError> for HandlerError {
    fn from(error: ProxyError) -> Self {
        Self::Internal(error)
    }
}

impl From<JsonRpcError> for HandlerError {
    fn from(error: JsonRpcError) -> Self {
        Self::JsonRpc(error_response(error))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use http::{Request, StatusCode};
    use rstest::rstest;
    use serde_json::{Value, json};
    use std::collections::HashSet;
    use tower::util::ServiceExt;

    #[tokio::test]
    async fn blocked_method_response_contains_message() {
        let response = blocked_method_response(&Value::from(1), "eth_sendTransaction");
        assert_eq!(response.status(), StatusCode::OK);
        let bytes = http_body_util::BodyExt::collect(response.into_body())
            .await
            .unwrap()
            .to_bytes();
        let value: Value = serde_json::from_slice(&bytes).unwrap();
        assert_eq!(value["error"]["code"], -32601);
        assert!(
            value["error"]["message"]
                .as_str()
                .unwrap()
                .contains("blocked")
        );
        assert_eq!(value["id"], 1);
    }

    #[rstest]
    fn build_uri_uses_incoming_path() {
        let base = "http://127.0.0.1:8545".parse::<Uri>().unwrap();
        let incoming = "http://localhost:3000/custom".parse::<Uri>().unwrap();
        let result = build_target_uri(&base, &incoming).unwrap();
        assert_eq!(result.to_string(), "http://127.0.0.1:8545/custom");
    }

    #[tokio::test]
    async fn end_to_end_blocks_configured_method() {
        let config = Config::new(
            "127.0.0.1:0".parse().unwrap(),
            "http://127.0.0.1:8545".parse().unwrap(),
            HashSet::from([String::from("eth_sendtransaction")]),
        );

        let state = AppState::try_from_config(config).unwrap();
        let app = router(state);
        let payload = json!({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "eth_sendTransaction",
            "params": []
        });

        let request = Request::builder()
            .method("POST")
            .uri("/")
            .header("content-type", "application/json")
            .body(Body::from(payload.to_string()))
            .unwrap();

        let response = app.clone().oneshot(request).await.expect("proxy response");
        assert_eq!(response.status(), StatusCode::OK);
        let bytes = http_body_util::BodyExt::collect(response.into_body())
            .await
            .unwrap()
            .to_bytes();
        let value: Value = serde_json::from_slice(&bytes).unwrap();
        assert_eq!(value["error"]["code"], -32601);
    }
}
