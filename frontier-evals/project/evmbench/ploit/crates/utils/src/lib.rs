#![doc = include_str!("../README.md")]
#![cfg_attr(docsrs, feature(doc_cfg, doc_auto_cfg))]
#![cfg_attr(not(feature = "std"), no_std)]

// Import tracing macros at the crate level
// This allows all modules in this crate to use debug!, info!, warn!, error!, trace!
// without the tracing:: prefix
#[cfg(feature = "std")]
#[macro_use]
extern crate tracing;

#[cfg(feature = "std")]
mod kill;
#[cfg(feature = "std")]
pub use kill::{KillConfig, KillService};

#[cfg(feature = "std")]
pub mod backtrace;

#[cfg(feature = "std")]
pub mod logging;

#[cfg(feature = "std")]
mod process;
#[cfg(feature = "std")]
pub use process::kill_port;

#[cfg(feature = "std")]
pub mod sigsegv_handler;

pub mod styles;
