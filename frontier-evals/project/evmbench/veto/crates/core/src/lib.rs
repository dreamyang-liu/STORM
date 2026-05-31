#![doc = include_str!("../README.md")]
#![cfg_attr(docsrs, feature(doc_cfg, doc_auto_cfg))]
#![cfg_attr(not(test), warn(unused_crate_dependencies))]

mod errors;
pub use errors::ProxyError;

mod jsonrpc;
pub use jsonrpc::{JsonRpcError, JsonRpcRequest};

mod runtime;
pub use runtime::run;

mod server;
pub use server::{AppState, router};
