use http::Uri;
use std::net::SocketAddr;

/// Overrides provided via the CLI.
#[derive(Debug, Clone, Default)]
pub struct Overrides {
    bind_address: Option<SocketAddr>,
    upstream_url: Option<Uri>,
    blocked_methods: Vec<String>,
}

impl Overrides {
    /// Create a new [`Overrides`] container around optional CLI values.
    pub const fn new(
        bind_address: Option<SocketAddr>,
        upstream_url: Option<Uri>,
        blocked_methods: Vec<String>,
    ) -> Self {
        Self {
            bind_address,
            upstream_url,
            blocked_methods,
        }
    }

    /// Returns `true` if no overriding values were provided.
    pub const fn is_empty(&self) -> bool {
        self.bind_address.is_none()
            && self.upstream_url.is_none()
            && self.blocked_methods.is_empty()
    }

    /// Accessor for the bind address override.
    pub const fn bind_address(&self) -> Option<SocketAddr> {
        self.bind_address
    }

    /// Accessor for the upstream URL override.
    pub const fn upstream_url(&self) -> Option<&Uri> {
        self.upstream_url.as_ref()
    }

    /// Borrow the blocked methods override.
    pub fn blocked_methods(&self) -> &[String] {
        &self.blocked_methods
    }
}
