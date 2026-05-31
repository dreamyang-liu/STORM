//! Telemetry initializers.

/// Initialize the tracing subscriber, honoring environment filters when provided.
pub(crate) fn init() {
    tracing::debug!("initializing tracing subscriber");

    let _ = tracing_subscriber::fmt()
        .with_env_filter(tracing_subscriber::EnvFilter::from_default_env())
        .with_target(false)
        .try_init();
}
