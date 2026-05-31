use crate::Config;
use crate::ConfigError;
use crate::FileConfig;
use crate::Overrides;
use crate::{DEFAULT_BIND_ADDRESS, DEFAULT_UPSTREAM_URL, default_blocked_methods};
use http::Uri;
use std::collections::HashSet;
use std::net::SocketAddr;
use std::str::FromStr;

/// Resolve the final configuration by merging file values with CLI overrides.
pub fn resolve_config(
    file: Option<FileConfig>,
    overrides: Overrides,
) -> Result<Config, ConfigError> {
    let (file_bind, file_upstream, file_methods) = match file {
        Some(cfg) => (
            cfg.bind_address,
            cfg.upstream_url,
            cfg.blocked_methods.unwrap_or_default(),
        ),
        None => (None, None, Vec::new()),
    };

    let bind_address = if let Some(addr) = overrides.bind_address() {
        addr
    } else if let Some(value) = file_bind.as_deref() {
        parse_socket_addr(value)?
    } else {
        parse_socket_addr(DEFAULT_BIND_ADDRESS)?
    };

    let upstream_url = if let Some(uri) = overrides.upstream_url().cloned() {
        uri
    } else if let Some(value) = file_upstream.as_deref() {
        parse_uri(value)?
    } else {
        parse_uri(DEFAULT_UPSTREAM_URL)?
    };

    let mut blocked_methods: HashSet<String> = default_blocked_methods()
        .map(|method| method.to_ascii_lowercase())
        .collect();
    blocked_methods.extend(
        file_methods
            .into_iter()
            .filter_map(|method| normalize_method(&method)),
    );
    blocked_methods.extend(
        overrides
            .blocked_methods()
            .iter()
            .filter_map(|method| normalize_method(method)),
    );

    Ok(Config::new(bind_address, upstream_url, blocked_methods))
}

fn parse_socket_addr(value: &str) -> Result<SocketAddr, ConfigError> {
    SocketAddr::from_str(value).map_err(|source| ConfigError::BindAddress {
        value: value.to_string(),
        source,
    })
}

fn parse_uri(value: &str) -> Result<Uri, ConfigError> {
    Uri::from_str(value).map_err(|source| ConfigError::UpstreamUrl {
        value: value.to_string(),
        source,
    })
}

fn normalize_method(value: &str) -> Option<String> {
    let normalized = value.trim().to_ascii_lowercase();
    if normalized.is_empty() {
        None
    } else {
        Some(normalized)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use rstest::rstest;

    #[rstest]
    fn default_resolution_without_inputs() {
        let config = resolve_config(None, Overrides::default()).expect("config resolves");
        assert_eq!(
            config.bind_address(),
            parse_socket_addr(DEFAULT_BIND_ADDRESS).unwrap()
        );
        assert_eq!(
            config.upstream_url(),
            &parse_uri(DEFAULT_UPSTREAM_URL).unwrap()
        );
        let expected: HashSet<String> = default_blocked_methods()
            .map(|method| method.to_ascii_lowercase())
            .collect();
        assert_eq!(config.blocked_methods(), &expected);
    }

    #[rstest]
    fn file_values_are_used() {
        let file = FileConfig {
            bind_address: Some("127.0.0.1:9000".to_string()),
            upstream_url: Some("http://127.0.0.1:9001".to_string()),
            blocked_methods: Some(vec!["eth_sendTransaction".into(), " personal_sign ".into()]),
        };
        let config = resolve_config(Some(file), Overrides::default()).expect("config resolves");
        assert_eq!(
            config.bind_address(),
            "127.0.0.1:9000".parse::<SocketAddr>().unwrap()
        );
        assert_eq!(
            config.upstream_url(),
            &"http://127.0.0.1:9001".parse::<Uri>().unwrap()
        );
        let methods = config.blocked_methods();
        assert!(methods.contains("eth_sendtransaction"));
        assert!(methods.contains("personal_sign"));
    }

    #[rstest]
    fn cli_overrides_take_precedence() {
        let file = FileConfig {
            bind_address: Some("127.0.0.1:9000".to_string()),
            upstream_url: Some("http://127.0.0.1:9001".to_string()),
            blocked_methods: Some(vec!["eth_sendtransaction".into()]),
        };

        let overrides = Overrides::new(
            Some("127.0.0.1:9100".parse().unwrap()),
            Some("http://127.0.0.1:9101".parse().unwrap()),
            vec!["eth_getBalance".into()],
        );

        let config = resolve_config(Some(file), overrides).expect("config resolves");

        assert_eq!(
            config.bind_address(),
            "127.0.0.1:9100".parse::<SocketAddr>().unwrap()
        );
        assert_eq!(
            config.upstream_url(),
            &"http://127.0.0.1:9101".parse::<Uri>().unwrap()
        );
        assert!(config.blocked_methods().contains("eth_sendtransaction"));
        assert!(config.blocked_methods().contains("eth_getbalance"));
    }

    #[rstest]
    fn invalid_bind_address_yields_error() {
        let file = FileConfig {
            bind_address: Some("not-an-addr".into()),
            ..Default::default()
        };

        let err = resolve_config(Some(file), Overrides::default()).unwrap_err();
        match err {
            ConfigError::BindAddress { value, .. } => assert_eq!(value, "not-an-addr"),
            other => panic!("unexpected error: {other:?}"),
        }
    }

    #[rstest]
    fn normalize_method_discards_empty_entries() {
        let file = FileConfig {
            bind_address: None,
            upstream_url: None,
            blocked_methods: Some(vec!["  ".into(), "eth_call".into()]),
        };

        let config = resolve_config(Some(file), Overrides::default()).expect("config resolves");
        let default_count = default_blocked_methods().count();
        assert_eq!(config.blocked_methods().len(), default_count + 1);
        assert!(config.blocked_methods().contains("eth_call"));
    }
}
