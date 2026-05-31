//! Constants used by the configuration.

/// Default socket address the proxy binds to.
pub const DEFAULT_BIND_ADDRESS: &str = "0.0.0.0:8546";

/// Default upstream JSON-RPC endpoint (Anvil).
pub const DEFAULT_UPSTREAM_URL: &str = "http://127.0.0.1:8545";

/// Default on-disk configuration file path.
pub const DEFAULT_CONFIG_PATH: &str = ".veto.toml";

/// Default Anvil-specific JSON-RPC methods blocked by the proxy.
pub const ANVIL_BLOCKED_METHODS: &[&str] = &[
    "anvil_autoImpersonateAccount",
    "anvil_dropTransaction",
    "anvil_dumpState",
    "anvil_enableTraces",
    "anvil_getAutomine",
    "anvil_impersonateAccount",
    "anvil_increaseTime",
    "anvil_loadState",
    "anvil_metadata",
    "anvil_mine",
    "anvil_mine_detailed",
    "anvil_nodeInfo",
    "anvil_removeBlockTimestampInterval",
    "anvil_reset",
    "anvil_revert",
    "anvil_setAutomine",
    "anvil_setBalance",
    "anvil_setBlockGasLimit",
    "anvil_setBlockTimestampInterval",
    "anvil_setChainId",
    "anvil_setCode",
    "anvil_setCoinbase",
    "anvil_setIntervalMining",
    "anvil_setLoggingEnabled",
    "anvil_setMinGasPrice",
    "anvil_setNextBlockBaseFeePerGas",
    "anvil_setNextBlockTimestamp",
    "anvil_setNonce",
    "anvil_setRpcUrl",
    "anvil_setStorageAt",
    "anvil_setTime",
    "anvil_snapshot",
    "anvil_stopImpersonatingAccount",
];

/// Default Hardhat-specific JSON-RPC helpers blocked by the proxy.
///
/// Note: Anvil implements a subset of these for compatibility, so blocking them
/// closes an easy "cheat path" even when the upstream is Anvil.
pub const HARDHAT_BLOCKED_METHODS: &[&str] = &[
    "hardhat_impersonateAccount",
    "hardhat_stopImpersonatingAccount",
    "hardhat_reset",
    "hardhat_mine",
    "hardhat_setBalance",
    "hardhat_setCode",
    "hardhat_setNonce",
    "hardhat_setStorageAt",
];

/// Default Hardhat/Ganache-style `evm_*` helpers blocked by the proxy.
pub const EVM_BLOCKED_METHODS: &[&str] = &[
    // "Time travel" / chain manipulation
    "evm_increaseTime",
    "evm_mine",
    "evm_reset",
    "evm_revert",
    "evm_setAutomine",
    // Direct account/state mutation (supported by some dev nodes / clients)
    "evm_setAccountBalance",
    "evm_setAccountCode",
    "evm_setAccountNonce",
    "evm_setAccountStorageAt",
    "evm_setBlockGasLimit",
    "evm_setIntervalMining",
    "evm_setNextBlockTimestamp",
    // Impersonation (supported by some dev nodes / clients)
    "evm_impersonateAccount",
    "evm_snapshot",
    "evm_stopImpersonatingAccount",
];

/// Returns an iterator over the default blocked JSON-RPC method names.
pub fn default_blocked_methods() -> impl Iterator<Item = &'static str> {
    ANVIL_BLOCKED_METHODS
        .iter()
        .chain(HARDHAT_BLOCKED_METHODS.iter())
        .chain(EVM_BLOCKED_METHODS.iter())
        .copied()
}
