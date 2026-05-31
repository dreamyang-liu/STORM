use std::collections::HashSet;
use veto_config::{
    ANVIL_BLOCKED_METHODS, EVM_BLOCKED_METHODS, HARDHAT_BLOCKED_METHODS, default_blocked_methods,
};

/// The list of Anvil-specific JSON-RPC helpers that are blocked by default.
pub const ANVIL_METHODS: &[&str] = ANVIL_BLOCKED_METHODS;

/// The list of Hardhat-specific JSON-RPC helpers that are blocked by default.
pub const HARDHAT_METHODS: &[&str] = HARDHAT_BLOCKED_METHODS;

/// The list of Hardhat/Ganache `evm_*` helpers that are blocked by default.
pub const EVM_METHODS: &[&str] = EVM_BLOCKED_METHODS;

/// Returns the full set of default blocked methods (Anvil + `hardhat_*` + `evm_*`).
pub fn blocked_method_set() -> HashSet<String> {
    default_blocked_methods()
        .map(|method| method.to_ascii_lowercase())
        .collect()
}

/// Return the ordered list of default blocked methods.
pub fn default_method_list() -> Vec<&'static str> {
    default_blocked_methods().collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn blocked_method_set_includes_anvil_and_evm_methods() {
        let blocked = blocked_method_set();
        assert!(blocked.contains("anvil_setbalance"));
        assert!(blocked.contains("evm_mine"));
    }
}
