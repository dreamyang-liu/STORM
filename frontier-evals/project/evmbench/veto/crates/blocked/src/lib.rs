#![doc = include_str!("../README.md")]
#![cfg_attr(docsrs, feature(doc_cfg, doc_auto_cfg))]
#![cfg_attr(not(test), warn(unused_crate_dependencies))]

mod anvil;
pub use anvil::AnvilBlocked;

mod methods;
pub use methods::{
    ANVIL_METHODS, EVM_METHODS, HARDHAT_METHODS, blocked_method_set, default_method_list,
};
