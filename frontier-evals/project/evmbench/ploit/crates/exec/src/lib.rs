#![doc = include_str!("../README.md")]
#![cfg_attr(docsrs, feature(doc_cfg, doc_auto_cfg))]
#![cfg_attr(not(feature = "std"), no_std)]

#[cfg(not(feature = "std"))]
extern crate alloc;

#[cfg(feature = "std")]
#[macro_use]
extern crate tracing;

mod executor;
pub use executor::Executor;

#[cfg(feature = "std")]
mod local;
#[cfg(feature = "std")]
pub use local::{LocalExecutor, LocalExecutorConfig};

#[cfg(feature = "std")]
mod result;
#[cfg(feature = "std")]
pub use result::ExecResult;
