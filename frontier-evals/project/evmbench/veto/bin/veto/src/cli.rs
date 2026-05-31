//! CLI entry point that resolves configuration and launches the proxy runtime.

use std::net::SocketAddr;
use std::path::{Path, PathBuf};

use anyhow::Result;
use clap::Parser;
use http::Uri;
use tracing::{debug, info, warn};
use veto_config::{Config, DEFAULT_CONFIG_PATH, FileConfig, Overrides, load_file, resolve_config};

/// Parse CLI arguments, resolve a [`Config`], and run the proxy.
pub(crate) async fn run() -> Result<()> {
    let cli = Cli::parse();
    debug!(config_path = %cli.config.display(), "parsed CLI arguments");
    let config = cli.resolve_configuration()?;

    log_configuration(&config);

    veto_core::run(config).await?;
    Ok(())
}

fn log_configuration(config: &Config) {
    info!(
        "starting proxy on http://{} forwarding to {}",
        config.bind_address(),
        config.upstream_url()
    );

    if config.blocked_methods().is_empty() {
        info!("no blocked methods configured");
    } else {
        let mut blocked: Vec<_> = config.blocked_methods().iter().cloned().collect();
        blocked.sort();
        info!("blocking methods: {}", blocked.join(", "));
    }
}

#[derive(Debug, Parser)]
#[command(
    author,
    version,
    about = "Ethereum JSON-RPC proxy with method filtering."
)]
struct Cli {
    /// Path to the TOML configuration file.
    #[arg(long, value_name = "PATH", default_value = DEFAULT_CONFIG_PATH)]
    config: PathBuf,

    /// Override the bind address for the proxy (e.g. 0.0.0.0:8546).
    #[arg(long, value_name = "ADDR")]
    bind_address: Option<SocketAddr>,

    /// Override the upstream Anvil endpoint (e.g. http://127.0.0.1:8545).
    #[arg(long, value_name = "URL")]
    upstream_url: Option<Uri>,

    /// Comma separated JSON-RPC method names to block.
    #[arg(long = "blocked-methods", value_delimiter = ',', value_name = "METHOD")]
    blocked_methods: Vec<String>,
}

impl Cli {
    /// Merge `.veto.toml` (if present) with CLI overrides into a [`Config`].
    fn resolve_configuration(&self) -> Result<Config> {
        let file_config = self.load_file_configuration()?;
        let overrides = Overrides::new(
            self.bind_address,
            self.upstream_url.clone(),
            self.blocked_methods.clone(),
        );

        if overrides.is_empty() {
            debug!("no CLI overrides supplied");
        } else {
            debug!(
                bind_override = ?self.bind_address,
                upstream_override = ?self.upstream_url,
                blocked_override_count = self.blocked_methods.len(),
                "applying CLI overrides"
            );
        }

        let config = resolve_config(file_config, overrides)?;
        debug!(
            bind_address = %config.bind_address(),
            upstream_url = %config.upstream_url(),
            blocked_methods = config.blocked_methods().len(),
            "resolved effective configuration"
        );

        Ok(config)
    }

    /// Attempt to load a [`FileConfig`] from disk.
    fn load_file_configuration(&self) -> Result<Option<FileConfig>> {
        let file_config = load_file(self.config.as_path())?;

        if let Some(ref file) = file_config {
            debug!(
                path = %self.config.display(),
                blocked_methods = file.blocked_methods.as_ref().map_or(0, |methods| methods.len()),
                "loaded configuration file"
            );
        }

        if file_config.is_none() && self.config.as_path() != Path::new(DEFAULT_CONFIG_PATH) {
            warn!(
                "configuration file {:?} not found; continuing with defaults and CLI overrides",
                self.config
            );
        }

        Ok(file_config)
    }
}
