//! Service for killing hanging processes.

use crate::kill_port;
use anyhow::{Context, Result};
use ploit_config::PloitConfig;
use std::path::PathBuf;

/// Configuration for the [`KillService`].
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct KillConfig {
    /// The port to kill processes on.
    pub port: Option<u16>,
    /// The path for the [`PloitConfig`] configuration file.
    ///
    /// [`PloitConfig`]: ploit_config::PloitConfig
    pub config_path: PathBuf,
}

impl KillConfig {
    /// Creates a new [`KillConfig`].
    ///
    /// # Arguments
    ///
    /// * `config_path` - Path to the [`PloitConfig`] configuration file
    /// * `port` - Optional port to kill processes on. If `None`, will use port from config
    ///
    /// [`PloitConfig`]: ploit_config::PloitConfig
    pub fn new(config_path: PathBuf, port: Option<u16>) -> Result<Self> {
        Ok(Self { config_path, port })
    }
}

/// Kill Service
///
/// Kills processes on the specified port or the port defined in the [`PloitConfig`] configuration file.
///
/// Uses [`kill_port`] internally to terminate processes.
///
/// [`PloitConfig`]: ploit_config::PloitConfig
/// [`kill_port`]: crate::kill_port
#[derive(Debug, Clone, PartialEq, Eq, derive_more::From)]
pub struct KillService {
    config: KillConfig,
}

impl KillService {
    /// Kills the process on the specified port or the port defined in the [`PloitConfig`] configuration file.
    ///
    /// # Returns
    ///
    /// Returns `Ok(())` on success, or an error if:
    /// - The configuration file cannot be loaded (when port is not specified)
    /// - The kill operation fails
    ///
    /// [`PloitConfig`]: ploit_config::PloitConfig
    pub async fn kill(&self) -> Result<()> {
        // Determine the port to kill
        let port = if let Some(p) = self.config.port {
            debug!("Using port {} from command line argument", p);
            p
        } else {
            // Load config to get the port
            let config = PloitConfig::load_or_default(&self.config.config_path)
                .context("Failed to load config file. Run 'ploit setup' first or specify --port")?;
            debug!("Using port {} from config file", config.anvil_port);
            config.anvil_port
        };

        debug!("Attempting to kill process on port {}", port);

        // Kill the process using the utility function
        kill_port(port)?;

        debug!("✓ Successfully killed process on port {}", port);
        Ok(())
    }
}
