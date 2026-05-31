use crate::methods::{
    ANVIL_METHODS, EVM_METHODS, HARDHAT_METHODS, blocked_method_set, default_method_list,
};
use http::Uri;
use std::net::SocketAddr;
use veto_config::Config;

/// Preconfigured Veto instance that blocks Anvil- and Hardhat-specific RPC helpers.
#[derive(Debug, Clone)]
pub struct AnvilBlocked {
    bind_address: SocketAddr,
    upstream_url: Uri,
}

impl AnvilBlocked {
    /// Create a new preset targeting the given upstream node.
    pub const fn new(bind_address: SocketAddr, upstream_url: Uri) -> Self {
        Self {
            bind_address,
            upstream_url,
        }
    }

    /// Socket address Veto should bind to.
    pub const fn bind_address(&self) -> SocketAddr {
        self.bind_address
    }

    /// Upstream Anvil endpoint URL.
    pub const fn upstream_url(&self) -> &Uri {
        &self.upstream_url
    }

    /// All JSON-RPC helpers blocked by this preset.
    pub fn methods() -> Vec<&'static str> {
        default_method_list()
    }

    /// Only the Anvil-specific methods blocked by this preset.
    pub const fn anvil_methods() -> &'static [&'static str] {
        ANVIL_METHODS
    }

    /// Only the Hardhat-specific methods blocked by this preset.
    pub const fn hardhat_methods() -> &'static [&'static str] {
        HARDHAT_METHODS
    }

    /// Hardhat/Ganache `evm_*` helpers blocked by this preset.
    pub const fn evm_methods() -> &'static [&'static str] {
        EVM_METHODS
    }

    /// Convert the preset into a [`Config`].
    pub fn into_config(self) -> Config {
        Config::new(self.bind_address, self.upstream_url, blocked_method_set())
    }

    /// Borrowed variant of [`into_config`](Self::into_config).
    pub fn to_config(&self) -> Config {
        Config::new(
            self.bind_address,
            self.upstream_url.clone(),
            blocked_method_set(),
        )
    }
}

impl From<AnvilBlocked> for Config {
    fn from(value: AnvilBlocked) -> Self {
        value.into_config()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn methods_include_anvil_hardhat_and_evm_helpers() {
        let methods = AnvilBlocked::methods();
        assert!(methods.contains(&"anvil_setBalance"));
        assert!(methods.contains(&"hardhat_setStorageAt"));
        assert!(methods.contains(&"evm_mine"));
    }
}
