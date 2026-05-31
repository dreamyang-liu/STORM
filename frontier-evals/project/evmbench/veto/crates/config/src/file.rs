use crate::ConfigError;
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::Path;

/// Representation of the on-disk `.veto.toml` configuration.
#[derive(Debug, Clone, Deserialize, Serialize, PartialEq, Eq, Default)]
pub struct FileConfig {
    /// Address the proxy should bind to.
    pub bind_address: Option<String>,
    /// Upstream Anvil endpoint.
    pub upstream_url: Option<String>,
    /// Methods to block when encountered in JSON-RPC payloads.
    pub blocked_methods: Option<Vec<String>>,
}

/// Parse and load the configuration file, returning `Ok(None)` when it is missing.
pub fn load_file(path: &Path) -> Result<Option<FileConfig>, ConfigError> {
    if !path.exists() {
        return Ok(None);
    }

    let contents = fs::read_to_string(path).map_err(|source| ConfigError::Io {
        path: path.to_path_buf(),
        source,
    })?;
    let parsed: FileConfig =
        toml::from_str(&contents).map_err(|source| ConfigError::TomlParse { source })?;
    Ok(Some(parsed))
}
