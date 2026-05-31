//! Result types for transaction execution.

use alloy_primitives::B256;

/// Result of re-executing a transaction.
///
/// Contains the original and new transaction hashes, execution status, and optional error information.
/// Returned by [`LocalExecutor`] when re-executing transactions.
///
/// [`LocalExecutor`]: crate::LocalExecutor
#[derive(Debug, Clone, Eq, PartialEq, serde::Serialize, serde::Deserialize)]
pub struct ExecResult {
    /// The original transaction hash from the input.
    pub original_hash: B256,
    /// The new transaction hash if re-execution was successful.
    pub new_hash: Option<B256>,
    /// The status of the re-execution (e.g., `"success"`, `"failed"`).
    pub status: String,
    /// An optional error message if the re-execution failed.
    pub error: Option<String>,
}
