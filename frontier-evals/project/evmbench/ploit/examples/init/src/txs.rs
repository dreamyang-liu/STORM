//! Handles transaction output.

use anyhow::Result;
use ploit_core::TransactionLoader;
use std::path::PathBuf;

/// Outputs transactions.
pub async fn txs() -> Result<()> {
    tracing::info!("Step 4: Listing transactions...");
    let loader = TransactionLoader::new(
        PathBuf::from(".ploit.toml").into(),
        Some("all".to_string()),
        None,
        None,
    );
    let txs = loader.load().await?;
    txs.write(&PathBuf::from("txs.json"))?;
    Ok(())
}
