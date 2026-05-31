//! The executor trait.

#[cfg(not(feature = "std"))]
use alloc::boxed::Box;

/// Executes transactions.
#[async_trait::async_trait]
pub trait Executor {
    /// Executes transactions as defined in a configured manner.
    ///
    /// # Returns
    ///
    /// A result indicating success or failure.
    async fn execute(&self) -> anyhow::Result<()>;
}
