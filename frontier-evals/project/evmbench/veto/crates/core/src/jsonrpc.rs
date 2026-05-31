use axum::body::Body;
use axum::http::StatusCode;
use axum::response::Response;
use serde::Deserialize;
use serde_json::{Value, json};

/// Inbound JSON-RPC request payload.
#[derive(Debug, Deserialize)]
pub struct JsonRpcRequest {
    /// Method invoked by the request.
    #[serde(default)]
    pub method: String,
    /// Identifier echoed back to the caller as a [`Value`].
    #[serde(default)]
    pub id: Value,
}

/// Errors produced while decoding JSON-RPC payloads.
#[derive(Debug)]
pub enum JsonRpcError {
    /// Error parsing JSON.
    InvalidJson(serde_json::Error),
    /// The request is not a valid JSON-RPC request.
    InvalidRequest(String),
    /// The request is a batch request, which is not supported.
    Unsupported(String),
}

/// Inbound JSON-RPC payload (single request or batch).
#[derive(Debug)]
pub enum JsonRpcPayload {
    Single(JsonRpcRequest),
    Batch(Vec<JsonRpcRequest>),
}

/// Parse bytes into a [`JsonRpcPayload`], validating empty methods.
pub(crate) fn parse_json_rpc(body: &[u8]) -> Result<JsonRpcPayload, JsonRpcError> {
    if body.is_empty() {
        return Err(JsonRpcError::InvalidRequest("empty body".into()));
    }

    let value: Value = serde_json::from_slice(body).map_err(JsonRpcError::InvalidJson)?;

    let payload = match value {
        Value::Object(_) => {
            let request: JsonRpcRequest = serde_json::from_value(value).map_err(JsonRpcError::InvalidJson)?;
            JsonRpcPayload::Single(request)
        }
        Value::Array(items) => {
            if items.is_empty() {
                return Err(JsonRpcError::InvalidRequest("empty batch".into()));
            }
            let mut requests = Vec::with_capacity(items.len());
            for item in items {
                match item {
                    Value::Object(_) => {
                        let request: JsonRpcRequest =
                            serde_json::from_value(item).map_err(JsonRpcError::InvalidJson)?;
                        requests.push(request);
                    }
                    _ => {
                        return Err(JsonRpcError::InvalidRequest(
                            "JSON-RPC batch elements must be objects".into(),
                        ));
                    }
                }
            }
            JsonRpcPayload::Batch(requests)
        }
        _ => {
            return Err(JsonRpcError::InvalidRequest(
                "JSON-RPC payload must be an object".into(),
            ));
        }
    };

    let validate_method = |method: &str| -> Result<(), JsonRpcError> {
        if method.trim().is_empty() {
            return Err(JsonRpcError::InvalidRequest(
                "JSON-RPC method is required".into(),
            ));
        }
        Ok(())
    };

    match &payload {
        JsonRpcPayload::Single(request) => validate_method(&request.method)?,
        JsonRpcPayload::Batch(requests) => {
            for request in requests {
                validate_method(&request.method)?;
            }
        }
    }

    Ok(payload)
}

/// Convert a [`JsonRpcError`] into a JSON-RPC response payload.
pub(crate) fn error_response(error: JsonRpcError) -> Response {
    let message = match &error {
        JsonRpcError::InvalidJson(err) => err.to_string(),
        JsonRpcError::InvalidRequest(message) | JsonRpcError::Unsupported(message) => {
            message.clone()
        }
    };

    let payload = json!({
        "jsonrpc": "2.0",
        "error": {
            "code": -32600,
            "message": message,
        },
        "id": Value::Null,
    });

    Response::builder()
        .status(StatusCode::BAD_REQUEST)
        .header("content-type", "application/json")
        .body(Body::from(payload.to_string()))
        .expect("valid json error response")
}
