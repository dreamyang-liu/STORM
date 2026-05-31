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
mod transactions;
#[cfg(feature = "std")]
pub use transactions::{TransactionLoader, Transactions, TxDetails};

#[cfg(feature = "std")]
mod addresses;
#[cfg(feature = "std")]
pub use addresses::{AddressLoader, Addresses};

#[cfg(feature = "std")]
mod setup;
#[cfg(feature = "std")]
pub use setup::{Setup, SetupConfig, SetupResult, display_port_conflict_help, is_port_available};
