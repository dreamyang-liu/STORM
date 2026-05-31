use crate::errors::ProxyError;
use crate::server::{AppState, router};
use axum::serve;
use tokio::net::TcpListener;
use tracing::{debug, error, info};
use veto_config::Config;

/// Run the proxy server with the provided [`Config`] until shutdown.
pub async fn run(config: Config) -> Result<(), ProxyError> {
    let state = AppState::try_from_config(config)?;
    let bind_address = state.bind_address();

    debug!(%bind_address, "binding proxy listener");
    let listener = TcpListener::bind(bind_address)
        .await
        .map_err(ProxyError::Bind)?;
    info!("veto proxy listening on http://{bind_address}");

    let router = router(state);
    serve(listener, router)
        .with_graceful_shutdown(shutdown_signal())
        .await
        .map_err(ProxyError::Server)
}

/// Await Ctrl+C and log the shutdown outcome.
async fn shutdown_signal() {
    match tokio::signal::ctrl_c().await {
        Ok(()) => info!("shutdown signal received"),
        Err(error) => error!("failed to listen for shutdown signal: {error}"),
    }
}
