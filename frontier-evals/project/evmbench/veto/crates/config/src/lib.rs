#![doc = include_str!("../README.md")]
#![cfg_attr(docsrs, feature(doc_cfg, doc_auto_cfg))]
#![cfg_attr(not(test), warn(unused_crate_dependencies))]

mod config;
pub use config::Config;

mod constants;
pub use constants::{
    ANVIL_BLOCKED_METHODS, DEFAULT_BIND_ADDRESS, DEFAULT_CONFIG_PATH, DEFAULT_UPSTREAM_URL,
    EVM_BLOCKED_METHODS, HARDHAT_BLOCKED_METHODS, default_blocked_methods,
};

mod errors;
pub use errors::ConfigError;

mod file;
pub use file::{FileConfig, load_file};

mod overrides;
pub use overrides::Overrides;

mod resolver;
pub use resolver::resolve_config;
