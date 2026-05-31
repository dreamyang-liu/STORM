use thiserror::Error;

/// Errors surfaced by the proxy runtime.
#[derive(Debug, Error)]
pub enum ProxyError {
    /// Failed to bind to the requested socket.
    #[error("failed to bind proxy socket: {0}")]
    Bind(std::io::Error),
    /// Axum server error.
    #[error("server error: {0}")]
    Server(std::io::Error),
    /// Body extraction failure.
    #[error("failed to read request body: {0}")]
    Body(Box<dyn std::error::Error + Send + Sync>),
    /// Failed to reach upstream.
    #[error("upstream request failed: {0}")]
    Upstream(hyper_util::client::legacy::Error),
    /// Failed to construct upstream URI for forwarding.
    #[error("failed to construct upstream URI: {0}")]
    BadUpstreamUri(http::uri::InvalidUriParts),
}
