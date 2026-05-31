use thiserror::Error;

/// Errors that can occur while loading or resolving the configuration.
#[derive(Debug, Error)]
pub enum ConfigError {
    /// Underlying IO failure.
    #[error("failed to read config file {path:?}: {source}")]
    Io {
        /// Path of the configuration file that could not be read.
        path: std::path::PathBuf,
        /// Underlying IO error produced while reading the file.
        source: std::io::Error,
    },
    /// Failure to parse TOML.
    #[error("unable to parse config file as TOML: {source}")]
    TomlParse {
        #[from]
        /// Error returned by the TOML parser.
        source: toml::de::Error,
    },
    /// Invalid socket address for bind.
    #[error("invalid bind address '{value}': {source}")]
    BindAddress {
        /// The offending bind address supplied by the user.
        value: String,
        /// Error returned while parsing the socket address.
        source: std::net::AddrParseError,
    },
    /// Invalid upstream URL.
    #[error("invalid upstream url '{value}': {source}")]
    UpstreamUrl {
        /// The upstream URL provided by the user.
        value: String,
        /// Error returned while parsing the URI.
        source: http::uri::InvalidUri,
    },
}
