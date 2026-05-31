use http::Uri;
use std::collections::HashSet;
use std::net::SocketAddr;

/// Fully resolved proxy configuration.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Config {
    bind_address: SocketAddr,
    upstream_url: Uri,
    blocked_methods: HashSet<String>,
}

impl Config {
    /// Construct a new [`Config`].
    pub const fn new(
        bind_address: SocketAddr,
        upstream_url: Uri,
        blocked_methods: HashSet<String>,
    ) -> Self {
        Self {
            bind_address,
            upstream_url,
            blocked_methods,
        }
    }

    /// Address the proxy server will bind to.
    pub const fn bind_address(&self) -> SocketAddr {
        self.bind_address
    }

    /// Upstream JSON-RPC endpoint.
    pub const fn upstream_url(&self) -> &Uri {
        &self.upstream_url
    }

    /// Blocked JSON-RPC method names (lowercase).
    pub const fn blocked_methods(&self) -> &HashSet<String> {
        &self.blocked_methods
    }
}
