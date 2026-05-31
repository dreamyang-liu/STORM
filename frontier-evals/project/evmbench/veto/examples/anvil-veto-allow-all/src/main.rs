//! Demonstrates how to run `veto` in front of an Anvil node while allowing
//! every custom `anvil_` JSON-RPC method.
//!
//! The example spins up:
//! 1. A disposable Anvil instance listening on a random localhost port.
//! 2. A `veto` proxy that forwards traffic to Anvil without blocking any method.
//! 3. A simple JSON-RPC client that calls each custom method via the proxy and
//!    prints the observed upstream response.
//!
//! The list of methods is sourced from the Anvil documentation:
//! <https://getfoundry.sh/anvil/reference#custom-methods>.
//! Running this example requires Anvil to be installed and available on `$PATH`
//! (e.g. via `foundryup`).

use anyhow::{Context, Result, anyhow, ensure};
use http::Uri;
use reqwest::{Client, StatusCode};
use serde_json::{Value, json};
use std::collections::HashSet;
use std::env;
use std::net::{SocketAddr, TcpListener};
use std::process::{Child, Command, Stdio};
use std::time::Duration;
use tokio::net::TcpStream;
use tokio::time::sleep;
use veto_config::Config;
use veto_core::run;

/// All documented Anvil custom RPC methods.
const CUSTOM_ANVIL_METHODS: &[&str] = &[
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

const TEST_ACCOUNT: &str = "0x1000000000000000000000000000000000000000";
const CODE_ACCOUNT: &str = "0x2000000000000000000000000000000000000000";
const COINBASE_ACCOUNT: &str = "0x3000000000000000000000000000000000000000";
const IMPERSONATED_ACCOUNT: &str = "0x4000000000000000000000000000000000000000";
const STORAGE_SLOT: &str = "0x0000000000000000000000000000000000000000000000000000000000000007";
const STORAGE_VALUE: &str = "0x000000000000000000000000000000000000000000000000000000000000dead";
const CONTRACT_CODE: &str = "0x600160005560016000f3";
const LOCAL_RPC_URL: &str = "http://127.0.0.1:8545";
const BASE_FEE_VALUE: u64 = 1_000_000_000;
const GAS_LIMIT_VALUE: u64 = 30_000_000;
const BLOCK_INTERVAL_SECS: u64 = 6;
const MIN_GAS_PRICE: u64 = 2_000_000_000;
const NEXT_BLOCK_TIMESTAMP_OFFSET: u64 = 42;
const TIME_RESET_VALUE: u64 = 1_700_000_000;
const NONCE_VALUE: u64 = 7;

#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::fmt::init();

    let anvil_port = reserve_port("Anvil")?;
    let proxy_port = reserve_port("veto proxy")?;

    let mut anvil = spawn_anvil(anvil_port)?;
    wait_for_port(SocketAddr::from(([127, 0, 0, 1], anvil_port)), "Anvil").await?;

    let proxy_addr = SocketAddr::from(([127, 0, 0, 1], proxy_port));
    let upstream: Uri = format!("http://127.0.0.1:{anvil_port}").parse().unwrap();
    let config = Config::new(proxy_addr, upstream, HashSet::new());

    let proxy_task = tokio::spawn(async move {
        if let Err(error) = run(config).await {
            eprintln!("veto proxy exited with error: {error}");
        }
    });
    wait_for_port(proxy_addr, "veto proxy").await?;

    println!("Proxy ready at http://{proxy_addr}");
    println!("Forwarded methods:");
    for method in CUSTOM_ANVIL_METHODS {
        println!("  - {method}");
    }
    println!();

    let forwarded = exercise_methods(proxy_addr).await?;

    println!("Forwarded responses:");
    for (method, summary) in forwarded {
        println!("{method}: {summary}");
    }

    proxy_task.abort();
    // Ignore errors: the task is aborted because the example is done.
    let _ = proxy_task.await;
    terminate(&mut anvil, "Anvil")?;

    Ok(())
}

fn reserve_port(reason: &str) -> Result<u16> {
    let listener = TcpListener::bind("127.0.0.1:0")
        .with_context(|| format!("failed to reserve a port for {reason}"))?;
    let port = listener
        .local_addr()
        .with_context(|| format!("failed to read local address for {reason} listener"))?
        .port();
    drop(listener);
    Ok(port)
}

fn spawn_anvil(port: u16) -> Result<Child> {
    let binary = env::var("ANVIL_BIN").unwrap_or_else(|_| "anvil".into());
    Command::new(binary)
        .arg("--host")
        .arg("127.0.0.1")
        .arg("--port")
        .arg(port.to_string())
        .arg("--silent")
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .context("failed to launch anvil")
}

async fn wait_for_port(address: SocketAddr, label: &str) -> Result<()> {
    for _ in 0..50 {
        if TcpStream::connect(address).await.is_ok() {
            return Ok(());
        }
        sleep(Duration::from_millis(100)).await;
    }

    Err(anyhow!("timed out waiting for {label} on {address}"))
}

async fn exercise_methods(address: SocketAddr) -> Result<Vec<(String, String)>> {
    ExerciseContext::create(address).await?.run().await
}

struct ExerciseContext {
    rpc: RpcClient,
    accounts: Vec<String>,
    default_sender: String,
    secondary_account: String,
    impersonated_active: bool,
    dump_state_blob: Option<String>,
    snapshot_id: Option<String>,
    initial_chain_id: String,
}

impl ExerciseContext {
    async fn create(address: SocketAddr) -> Result<Self> {
        let rpc = RpcClient::new(address);
        let accounts = rpc.eth_accounts().await?;
        ensure!(
            accounts.len() >= 2,
            "Anvil must provide at least two unlocked accounts"
        );
        let initial_chain_id = rpc.eth_chain_id().await?;

        Ok(Self {
            rpc,
            default_sender: accounts[0].clone(),
            secondary_account: accounts[1].clone(),
            accounts,
            impersonated_active: false,
            dump_state_blob: None,
            snapshot_id: None,
            initial_chain_id,
        })
    }

    async fn run(mut self) -> Result<Vec<(String, String)>> {
        let mut results = Vec::with_capacity(CUSTOM_ANVIL_METHODS.len());
        for method in CUSTOM_ANVIL_METHODS {
            let summary = match *method {
                "anvil_autoImpersonateAccount" => self.check_auto_impersonate().await?,
                "anvil_dropTransaction" => self.check_drop_transaction().await?,
                "anvil_dumpState" => self.check_dump_state().await?,
                "anvil_enableTraces" => self.check_enable_traces().await?,
                "anvil_getAutomine" => self.check_get_automine().await?,
                "anvil_impersonateAccount" => self.check_impersonate_account().await?,
                "anvil_increaseTime" => self.check_increase_time().await?,
                "anvil_loadState" => self.check_load_state().await?,
                "anvil_metadata" => self.check_metadata().await?,
                "anvil_mine" => self.check_mine().await?,
                "anvil_mine_detailed" => self.check_mine_detailed().await?,
                "anvil_nodeInfo" => self.check_node_info().await?,
                "anvil_removeBlockTimestampInterval" => {
                    self.check_remove_block_timestamp_interval().await?
                }
                "anvil_reset" => self.check_reset().await?,
                "anvil_revert" => self.check_revert().await?,
                "anvil_setAutomine" => self.check_set_automine().await?,
                "anvil_setBalance" => self.check_set_balance().await?,
                "anvil_setBlockGasLimit" => self.check_set_block_gas_limit().await?,
                "anvil_setBlockTimestampInterval" => {
                    self.check_set_block_timestamp_interval().await?
                }
                "anvil_setChainId" => self.check_set_chain_id().await?,
                "anvil_setCode" => self.check_set_code().await?,
                "anvil_setCoinbase" => self.check_set_coinbase().await?,
                "anvil_setIntervalMining" => self.check_set_interval_mining().await?,
                "anvil_setLoggingEnabled" => self.check_set_logging_enabled().await?,
                "anvil_setMinGasPrice" => self.check_set_min_gas_price().await?,
                "anvil_setNextBlockBaseFeePerGas" => self.check_set_next_block_base_fee().await?,
                "anvil_setNextBlockTimestamp" => self.check_set_next_block_timestamp().await?,
                "anvil_setNonce" => self.check_set_nonce().await?,
                "anvil_setRpcUrl" => self.check_set_rpc_url().await?,
                "anvil_setStorageAt" => self.check_set_storage_at().await?,
                "anvil_setTime" => self.check_set_time().await?,
                "anvil_snapshot" => self.check_snapshot().await?,
                "anvil_stopImpersonatingAccount" => self.check_stop_impersonating_account().await?,
                other => anyhow::bail!("Unhandled method {other}"),
            };
            results.push((method.to_string(), summary));
        }
        Ok(results)
    }

    async fn disable_auto_impersonate(&self) -> Result<()> {
        self.rpc
            .call_result("anvil_autoImpersonateAccount", vec![Value::Bool(false)])
            .await?;
        Ok(())
    }

    async fn enable_auto_impersonate(&self) -> Result<Value> {
        self.rpc
            .call_result("anvil_autoImpersonateAccount", vec![Value::Bool(true)])
            .await
    }

    async fn check_auto_impersonate(&mut self) -> Result<String> {
        let result = self.enable_auto_impersonate().await?;
        ensure!(
            result.is_null(),
            "expected null result enabling auto impersonation"
        );
        self.disable_auto_impersonate().await?;
        Ok("toggled auto impersonation on and back off".into())
    }

    async fn check_drop_transaction(&mut self) -> Result<String> {
        // disable automine to keep the transaction pending
        self.set_automine(false).await?;

        let tx_hash = self
            .send_transaction(&self.default_sender, &self.secondary_account, 0x1000_0000)
            .await?;

        let response = self
            .rpc
            .call_result(
                "anvil_dropTransaction",
                vec![Value::String(tx_hash.clone())],
            )
            .await?;
        let dropped = response
            .as_str()
            .context("dropTransaction should return the dropped hash")?;

        ensure!(
            dropped.eq_ignore_ascii_case(&tx_hash),
            "dropTransaction returned unexpected hash"
        );

        self.set_automine(true).await?;
        Ok(format!("dropped pending tx {dropped}"))
    }

    async fn check_dump_state(&mut self) -> Result<String> {
        let response = self.rpc.call_result("anvil_dumpState", vec![]).await?;
        let blob = response
            .as_str()
            .context("dumpState result must be a hex string")?;
        ensure!(blob.starts_with("0x"), "dumpState returned non-hex data");
        ensure!(blob.len() > 2, "dumpState returned empty payload");
        self.dump_state_blob = Some(blob.to_string());
        Ok(format!("dumped state ({})", summarize_hex(blob, 32)))
    }

    async fn check_enable_traces(&self) -> Result<String> {
        let response = self.rpc.call("anvil_enableTraces", vec![]).await?;
        if let Some(error) = response.body.get("error") {
            let message = error
                .get("message")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .to_string();
            ensure!(
                message.contains("Not implemented"),
                "unexpected error from anvil_enableTraces: {message}"
            );
            return Ok(
                "anvil_enableTraces not implemented upstream (proxy forwarding verified)".into(),
            );
        }
        let result = ensure_success("anvil_enableTraces", &response)?;
        ensure!(result.is_null(), "enableTraces should return null");
        Ok("enabled transaction traces".into())
    }

    async fn check_get_automine(&self) -> Result<String> {
        let result = self.rpc.call_result("anvil_getAutomine", vec![]).await?;
        let automine = result
            .as_bool()
            .context("getAutomine must return a boolean")?;
        Ok(format!("automine currently {}", automine))
    }

    async fn check_impersonate_account(&mut self) -> Result<String> {
        let result = self
            .rpc
            .call_result(
                "anvil_impersonateAccount",
                vec![Value::String(IMPERSONATED_ACCOUNT.into())],
            )
            .await?;
        ensure!(result.is_null(), "impersonateAccount should return null");
        self.impersonated_active = true;

        let accounts = self.rpc.eth_accounts().await?;
        ensure!(
            accounts
                .iter()
                .any(|account| account.eq_ignore_ascii_case(IMPERSONATED_ACCOUNT)),
            "impersonated account not returned by eth_accounts"
        );

        Ok("impersonated account added to eth_accounts".into())
    }

    async fn check_increase_time(&self) -> Result<String> {
        let result = self
            .rpc
            .call_result("anvil_increaseTime", vec![json!(BLOCK_INTERVAL_SECS)])
            .await?;
        let delta = value_to_i64(&result)?;
        ensure!(delta >= 0, "increaseTime returned negative value");
        Ok(format!("advanced time by {} seconds", delta))
    }

    async fn check_load_state(&mut self) -> Result<String> {
        let blob = self
            .dump_state_blob
            .as_ref()
            .context("dumpState must run before loadState")?;
        let result = self
            .rpc
            .call_result("anvil_loadState", vec![Value::String(blob.clone())])
            .await?;
        ensure!(
            result.is_null() || result == Value::Bool(true),
            "unexpected loadState result: {result}"
        );
        let outcome = if result.is_null() { "null" } else { "true" };
        Ok(format!(
            "loaded state blob back into the node (result {outcome})"
        ))
    }

    async fn check_metadata(&self) -> Result<String> {
        let result = self.rpc.call_result("anvil_metadata", vec![]).await?;
        ensure!(result.is_object(), "metadata should return an object");
        let keys = result
            .as_object()
            .unwrap()
            .keys()
            .cloned()
            .collect::<Vec<_>>();
        Ok(format!("metadata fields: {}", keys.join(", ")))
    }

    async fn check_mine(&self) -> Result<String> {
        let before = self.block_number().await?;
        let result = self.rpc.call_result("anvil_mine", vec![]).await?;
        match result {
            Value::String(_) | Value::Null => {}
            ref other => anyhow::bail!("unexpected anvil_mine result: {other}"),
        }
        let after = self.block_number().await?;
        ensure!(
            after == before + 1,
            "anvil_mine should mine exactly one block"
        );
        Ok(format!("mined block #{}", after))
    }

    async fn check_mine_detailed(&self) -> Result<String> {
        let before = self.block_number().await?;
        let result = self.rpc.call_result("anvil_mine_detailed", vec![]).await?;
        let mined = result
            .as_array()
            .context("anvil_mine_detailed should return an array")?;
        ensure!(mined.len() == 1, "expected single block from mine_detailed");
        let after = self.block_number().await?;
        ensure!(
            after == before + 1,
            "anvil_mine_detailed must mine one block"
        );
        Ok("mined_detailed returned 1 block".into())
    }

    async fn check_node_info(&self) -> Result<String> {
        let result = self.rpc.call_result("anvil_nodeInfo", vec![]).await?;
        ensure!(result.is_object(), "nodeInfo should return an object");
        let keys = result
            .as_object()
            .unwrap()
            .keys()
            .cloned()
            .collect::<Vec<_>>();
        Ok(format!("nodeInfo fields: {}", keys.join(", ")))
    }

    async fn check_remove_block_timestamp_interval(&self) -> Result<String> {
        self.rpc
            .call_result(
                "anvil_setBlockTimestampInterval",
                vec![json!(BLOCK_INTERVAL_SECS)],
            )
            .await?;
        let result = self
            .rpc
            .call_result("anvil_removeBlockTimestampInterval", vec![])
            .await?;
        let removed = result
            .as_bool()
            .context("removeBlockTimestampInterval should return bool")?;
        ensure!(
            removed,
            "expected removal of previously configured interval"
        );
        Ok("cleared block timestamp interval".into())
    }

    async fn check_reset(&mut self) -> Result<String> {
        let response = self.rpc.call("anvil_reset", vec![]).await?;
        if let Some(error) = response.body.get("error") {
            let message = error
                .get("message")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .to_string();
            ensure!(
                message.contains("Not implemented"),
                "unexpected error from anvil_reset: {message}"
            );
            return Ok(
                "anvil_reset not implemented in this Anvil build (proxy forwarding verified)"
                    .into(),
            );
        }

        let result = ensure_success("anvil_reset", &response)?;
        ensure!(result.is_null(), "reset should return null");
        let block_number = self.block_number().await?;
        ensure!(block_number <= 1, "reset should roll back to genesis");

        self.impersonated_active = false;
        self.snapshot_id = None;
        self.dump_state_blob = None;
        self.accounts = self.rpc.eth_accounts().await?;

        Ok("reset node back to genesis state".into())
    }

    async fn check_revert(&mut self) -> Result<String> {
        let snapshot = self
            .rpc
            .call_result("anvil_snapshot", vec![])
            .await?
            .as_str()
            .context("snapshot should return id string")?
            .to_string();
        let before = self.block_number().await?;
        self.mine_blocks(1).await?;
        let mined = self.block_number().await?;
        ensure!(mined == before + 1, "expected intermediate mined block");

        let result = self
            .rpc
            .call_result("anvil_revert", vec![Value::String(snapshot.clone())])
            .await?;
        ensure!(
            result.as_bool() == Some(true),
            "revert should return true for valid snapshot"
        );
        let after = self.block_number().await?;
        ensure!(after == before, "revert must restore previous block number");
        Ok(format!("reverted snapshot {snapshot}"))
    }

    async fn check_set_automine(&self) -> Result<String> {
        self.set_automine(false).await?;
        let status = self.rpc.call_result("anvil_getAutomine", vec![]).await?;
        ensure!(status.as_bool() == Some(false), "automine was not disabled");
        self.set_automine(true).await?;
        Ok("disabled then re-enabled automine".into())
    }

    async fn check_set_balance(&self) -> Result<String> {
        let value_hex = to_hex(MIN_GAS_PRICE);
        self.rpc
            .call_result(
                "anvil_setBalance",
                vec![
                    Value::String(TEST_ACCOUNT.into()),
                    Value::String(value_hex.clone()),
                ],
            )
            .await?;
        let balance = self
            .rpc
            .call_result(
                "eth_getBalance",
                vec![
                    Value::String(TEST_ACCOUNT.into()),
                    Value::String("latest".into()),
                ],
            )
            .await?;
        let balance_hex = balance
            .as_str()
            .context("eth_getBalance should return hex string")?;
        ensure!(
            normalize_hex(balance_hex) == normalize_hex(&value_hex),
            "setBalance did not persist"
        );
        Ok(format!("balance at {TEST_ACCOUNT} set to {value_hex}"))
    }

    async fn check_set_block_gas_limit(&self) -> Result<String> {
        let gas_limit_hex = to_hex(GAS_LIMIT_VALUE);
        self.rpc
            .call_result(
                "anvil_setBlockGasLimit",
                vec![Value::String(gas_limit_hex.clone())],
            )
            .await?;
        self.mine_blocks(1).await?;
        let latest = self.latest_block(false).await?;
        let limit = latest
            .get("gasLimit")
            .and_then(Value::as_str)
            .context("latest block missing gasLimit")?;
        ensure!(
            normalize_hex(limit) == normalize_hex(&gas_limit_hex),
            "gas limit not applied to latest block"
        );
        Ok(format!("next block gas limit set to {gas_limit_hex}"))
    }

    async fn check_set_block_timestamp_interval(&self) -> Result<String> {
        self.rpc
            .call_result(
                "anvil_setBlockTimestampInterval",
                vec![json!(BLOCK_INTERVAL_SECS)],
            )
            .await?;
        let ts_before = self.latest_timestamp().await?;
        self.mine_blocks(1).await?;
        let ts_after = self.latest_timestamp().await?;
        ensure!(
            ts_after >= ts_before + BLOCK_INTERVAL_SECS,
            "expected timestamp interval adjustment"
        );
        self.rpc
            .call_result("anvil_removeBlockTimestampInterval", vec![])
            .await?;
        Ok(format!(
            "timestamp interval applied (delta {} seconds)",
            ts_after - ts_before
        ))
    }

    async fn check_set_chain_id(&mut self) -> Result<String> {
        let new_chain_id = 9_999_u64;
        let original = parse_hex_u64(&self.initial_chain_id)?;
        self.rpc
            .call_result("anvil_setChainId", vec![json!(new_chain_id)])
            .await?;
        let chain_id = self.rpc.eth_chain_id().await?;
        ensure!(
            normalize_hex(&chain_id) == normalize_hex(&to_hex(new_chain_id)),
            "chain id not updated"
        );
        self.rpc
            .call_result("anvil_setChainId", vec![json!(original)])
            .await?;
        Ok(format!("chain id updated to {chain_id}"))
    }

    async fn check_set_code(&self) -> Result<String> {
        self.rpc
            .call_result(
                "anvil_setCode",
                vec![
                    Value::String(CODE_ACCOUNT.into()),
                    Value::String(CONTRACT_CODE.into()),
                ],
            )
            .await?;
        let code = self
            .rpc
            .call_result(
                "eth_getCode",
                vec![
                    Value::String(CODE_ACCOUNT.into()),
                    Value::String("latest".into()),
                ],
            )
            .await?;
        let code_hex = code
            .as_str()
            .context("eth_getCode should return hex string")?;
        ensure!(
            normalize_hex(code_hex) == normalize_hex(CONTRACT_CODE),
            "setCode did not persist"
        );
        Ok(format!(
            "code at {CODE_ACCOUNT} now {}",
            summarize_hex(code_hex, 18)
        ))
    }

    async fn check_set_coinbase(&self) -> Result<String> {
        self.rpc
            .call_result(
                "anvil_setCoinbase",
                vec![Value::String(COINBASE_ACCOUNT.into())],
            )
            .await?;
        self.mine_blocks(1).await?;
        let latest = self.latest_block(false).await?;
        let miner = latest
            .get("miner")
            .or_else(|| latest.get("author"))
            .and_then(Value::as_str)
            .context("latest block missing miner/author")?;
        ensure!(
            miner.eq_ignore_ascii_case(COINBASE_ACCOUNT),
            "coinbase not reflected in latest block"
        );
        Ok(format!("coinbase set to {COINBASE_ACCOUNT}"))
    }

    async fn check_set_interval_mining(&self) -> Result<String> {
        self.rpc
            .call_result("anvil_setIntervalMining", vec![json!(BLOCK_INTERVAL_SECS)])
            .await?;
        let status = self.rpc.call_result("anvil_getAutomine", vec![]).await?;
        ensure!(
            status.as_bool() == Some(false),
            "interval mining should disable automine"
        );
        self.set_automine(true).await?;
        Ok(format!(
            "interval mining {} seconds configured",
            BLOCK_INTERVAL_SECS
        ))
    }

    async fn check_set_logging_enabled(&self) -> Result<String> {
        self.rpc
            .call_result("anvil_setLoggingEnabled", vec![Value::Bool(false)])
            .await?;
        self.rpc
            .call_result("anvil_setLoggingEnabled", vec![Value::Bool(true)])
            .await?;
        Ok("toggled logging off then on".into())
    }

    async fn check_set_min_gas_price(&self) -> Result<String> {
        let price_hex = to_hex(MIN_GAS_PRICE);
        let response = self
            .rpc
            .call(
                "anvil_setMinGasPrice",
                vec![Value::String(price_hex.clone())],
            )
            .await?;
        if let Some(error) = response.body.get("error") {
            let message = error
                .get("message")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .to_string();
            ensure!(
                message.contains("EIP-1559"),
                "unexpected error from anvil_setMinGasPrice: {message}"
            );
            return Ok(
                "min gas price unsupported with EIP-1559 (proxy forwarding verified)".into(),
            );
        }
        let _ = ensure_success("anvil_setMinGasPrice", &response)?;
        let gas_price = self.rpc.eth_gas_price().await?;
        ensure!(
            hex_to_u64(&gas_price)? >= MIN_GAS_PRICE,
            "min gas price not applied"
        );
        Ok(format!("min gas price set to {price_hex}"))
    }

    async fn check_set_next_block_base_fee(&self) -> Result<String> {
        let base_fee_hex = to_hex(BASE_FEE_VALUE);
        self.rpc
            .call_result(
                "anvil_setNextBlockBaseFeePerGas",
                vec![Value::String(base_fee_hex.clone())],
            )
            .await?;
        self.mine_blocks(1).await?;
        let latest = self.latest_block(false).await?;
        let base_fee = latest
            .get("baseFeePerGas")
            .and_then(Value::as_str)
            .context("latest block missing baseFeePerGas")?;
        ensure!(
            normalize_hex(base_fee) == normalize_hex(&base_fee_hex),
            "base fee not set on next block"
        );
        Ok(format!("next block base fee set to {base_fee_hex}"))
    }

    async fn check_set_next_block_timestamp(&self) -> Result<String> {
        let current = self.latest_timestamp().await?;
        let next = current + NEXT_BLOCK_TIMESTAMP_OFFSET;
        self.rpc
            .call_result(
                "anvil_setNextBlockTimestamp",
                vec![Value::String(to_hex(next))],
            )
            .await?;
        self.mine_blocks(1).await?;
        let latest = self.latest_timestamp().await?;
        ensure!(
            latest == next,
            "next block timestamp not honored (expected {next}, got {latest})"
        );
        Ok(format!("next block timestamp forced to {next}"))
    }

    async fn check_set_nonce(&self) -> Result<String> {
        let nonce_hex = to_hex(NONCE_VALUE);
        self.rpc
            .call_result(
                "anvil_setNonce",
                vec![
                    Value::String(TEST_ACCOUNT.into()),
                    Value::String(nonce_hex.clone()),
                ],
            )
            .await?;
        let nonce = self
            .rpc
            .call_result(
                "eth_getTransactionCount",
                vec![
                    Value::String(TEST_ACCOUNT.into()),
                    Value::String("latest".into()),
                ],
            )
            .await?;
        ensure!(
            normalize_hex(nonce.as_str().context("nonce must be hex")?)
                == normalize_hex(&nonce_hex),
            "setNonce did not update tx count"
        );
        Ok(format!("nonce for {TEST_ACCOUNT} set to {nonce_hex}"))
    }

    async fn check_set_rpc_url(&self) -> Result<String> {
        let result = self
            .rpc
            .call_result("anvil_setRpcUrl", vec![Value::String(LOCAL_RPC_URL.into())])
            .await?;
        ensure!(result.is_null(), "setRpcUrl should return null");
        Ok(format!("set upstream RPC URL to {LOCAL_RPC_URL}"))
    }

    async fn check_set_storage_at(&self) -> Result<String> {
        self.rpc
            .call_result(
                "anvil_setStorageAt",
                vec![
                    Value::String(CODE_ACCOUNT.into()),
                    Value::String(STORAGE_SLOT.into()),
                    Value::String(STORAGE_VALUE.into()),
                ],
            )
            .await?;
        let storage = self
            .rpc
            .call_result(
                "eth_getStorageAt",
                vec![
                    Value::String(CODE_ACCOUNT.into()),
                    Value::String(STORAGE_SLOT.into()),
                    Value::String("latest".into()),
                ],
            )
            .await?;
        ensure!(
            normalize_hex(
                storage
                    .as_str()
                    .context("eth_getStorageAt should return hex")?
            ) == normalize_hex(STORAGE_VALUE),
            "storage slot not updated"
        );
        Ok(format!(
            "storage slot {} now {}",
            STORAGE_SLOT,
            summarize_hex(STORAGE_VALUE, 10)
        ))
    }

    async fn check_set_time(&self) -> Result<String> {
        let response = self
            .rpc
            .call_result(
                "anvil_setTime",
                vec![Value::String(to_hex(TIME_RESET_VALUE))],
            )
            .await?;
        let delta = response
            .as_u64()
            .context("setTime should return a u64 delta")?;
        self.mine_blocks(1).await?;
        let timestamp = self.latest_timestamp().await?;
        ensure!(
            timestamp >= TIME_RESET_VALUE,
            "setTime should advance clock (current {timestamp})"
        );
        Ok(format!(
            "set time to {} (delta {} seconds)",
            timestamp, delta
        ))
    }

    async fn check_snapshot(&mut self) -> Result<String> {
        let snapshot = self
            .rpc
            .call_result("anvil_snapshot", vec![])
            .await?
            .as_str()
            .context("snapshot should return id")?
            .to_string();
        self.snapshot_id = Some(snapshot.clone());
        Ok(format!("created snapshot {snapshot}"))
    }

    async fn check_stop_impersonating_account(&mut self) -> Result<String> {
        if !self.impersonated_active {
            self.rpc
                .call_result(
                    "anvil_impersonateAccount",
                    vec![Value::String(IMPERSONATED_ACCOUNT.into())],
                )
                .await?;
            self.impersonated_active = true;
        }

        let result = self
            .rpc
            .call_result(
                "anvil_stopImpersonatingAccount",
                vec![Value::String(IMPERSONATED_ACCOUNT.into())],
            )
            .await?;
        ensure!(
            result.is_null(),
            "stopImpersonatingAccount should return null"
        );
        self.impersonated_active = false;

        let accounts = self.rpc.eth_accounts().await?;
        ensure!(
            !accounts
                .iter()
                .any(|account| account.eq_ignore_ascii_case(IMPERSONATED_ACCOUNT)),
            "impersonated account should be removed"
        );

        Ok("stopped impersonating the test account".into())
    }

    async fn set_automine(&self, enabled: bool) -> Result<()> {
        self.rpc
            .call_result("anvil_setAutomine", vec![Value::Bool(enabled)])
            .await?;
        Ok(())
    }

    async fn mine_blocks(&self, count: u64) -> Result<()> {
        if count == 0 {
            return Ok(());
        }
        let params = if count == 1 {
            vec![]
        } else {
            vec![Value::String(to_hex(count))]
        };
        self.rpc.call_result("anvil_mine", params).await?;
        Ok(())
    }

    async fn send_transaction(&self, from: &str, to: &str, value: u64) -> Result<String> {
        let tx = json!({
            "from": from,
            "to": to,
            "gas": "0x5208",
            "gasPrice": to_hex(1_000_000_000),
            "value": to_hex(value),
        });
        let result = self
            .rpc
            .call_result("eth_sendTransaction", vec![tx])
            .await?;
        Ok(result
            .as_str()
            .context("eth_sendTransaction should return tx hash")?
            .to_string())
    }

    async fn block_number(&self) -> Result<u64> {
        let result = self.rpc.call_result("eth_blockNumber", vec![]).await?;
        let hex = result
            .as_str()
            .context("eth_blockNumber should return hex string")?;
        parse_hex_u64(hex)
    }

    async fn latest_block(&self, full: bool) -> Result<Value> {
        self.rpc
            .call_result(
                "eth_getBlockByNumber",
                vec![Value::String("latest".into()), Value::Bool(full)],
            )
            .await
    }

    async fn latest_timestamp(&self) -> Result<u64> {
        let block = self.latest_block(false).await?;
        let timestamp = block
            .get("timestamp")
            .and_then(Value::as_str)
            .context("latest block missing timestamp")?;
        parse_hex_u64(timestamp)
    }
}

struct RpcClient {
    client: Client,
    url: String,
}

struct RpcResponse {
    status: StatusCode,
    body: Value,
}

impl RpcClient {
    fn new(address: SocketAddr) -> Self {
        Self {
            client: Client::new(),
            url: format!("http://{address}"),
        }
    }

    async fn call(&self, method: &str, params: Vec<Value>) -> Result<RpcResponse> {
        let payload = json!({
            "jsonrpc": "2.0",
            "id": method,
            "method": method,
            "params": Value::Array(params),
        });

        let response = self
            .client
            .post(&self.url)
            .header("content-type", "application/json")
            .body(payload.to_string())
            .send()
            .await
            .with_context(|| format!("proxy call for {method} failed"))?;
        let status = response.status();
        let body: Value = response
            .json()
            .await
            .with_context(|| format!("proxy response for {method} was not JSON"))?;
        Ok(RpcResponse { status, body })
    }

    async fn call_result(&self, method: &str, params: Vec<Value>) -> Result<Value> {
        let response = self.call(method, params).await?;
        let result = ensure_success(method, &response)?;
        Ok(result.clone())
    }

    async fn eth_accounts(&self) -> Result<Vec<String>> {
        let result = self.call_result("eth_accounts", vec![]).await?;
        let accounts = result
            .as_array()
            .context("eth_accounts should return an array")?
            .iter()
            .map(|value| {
                value
                    .as_str()
                    .map(|s| s.to_string())
                    .context("eth_accounts entries must be strings")
            })
            .collect::<Result<Vec<_>>>()?;
        Ok(accounts)
    }

    async fn eth_chain_id(&self) -> Result<String> {
        let result = self.call_result("eth_chainId", vec![]).await?;
        result
            .as_str()
            .map(|s| s.to_string())
            .context("eth_chainId should return a hex string")
    }

    async fn eth_gas_price(&self) -> Result<String> {
        let result = self.call_result("eth_gasPrice", vec![]).await?;
        result
            .as_str()
            .map(|s| s.to_string())
            .context("eth_gasPrice should return hex string")
    }
}

fn ensure_success<'a>(method: &str, response: &'a RpcResponse) -> Result<&'a Value> {
    ensure!(
        response.status.is_success(),
        "proxy returned HTTP {} for {method}",
        response.status
    );
    if let Some(error) = response.body.get("error") {
        let message = error
            .get("message")
            .and_then(Value::as_str)
            .unwrap_or("unknown error");
        anyhow::bail!("method {method} returned error: {message}");
    }
    response
        .body
        .get("result")
        .ok_or_else(|| anyhow!("missing result field for {method}"))
}

fn parse_hex_u64(hex: &str) -> Result<u64> {
    let trimmed = hex
        .strip_prefix("0x")
        .unwrap_or(hex)
        .trim_start_matches('0');
    if trimmed.is_empty() {
        return Ok(0);
    }
    u64::from_str_radix(trimmed, 16).with_context(|| format!("failed to parse hex number {hex}"))
}

fn hex_to_u64(hex: &str) -> Result<u64> {
    parse_hex_u64(hex)
}

fn value_to_i64(value: &Value) -> Result<i64> {
    value
        .as_i64()
        .or_else(|| value.as_u64().map(|v| v as i64))
        .context("expected numeric result")
}

fn to_hex(value: u64) -> String {
    format!("0x{:x}", value)
}

fn normalize_hex(hex: &str) -> String {
    let mut normalized = String::from("0x");
    let digits = hex
        .strip_prefix("0x")
        .unwrap_or(hex)
        .trim_start_matches('0');
    if digits.is_empty() {
        normalized.push('0');
    } else {
        normalized.push_str(digits);
    }
    normalized
}

fn summarize_hex(value: &str, keep: usize) -> String {
    let digits = value.strip_prefix("0x").unwrap_or(value);
    if digits.len() <= keep {
        return value.to_string();
    }
    format!("0x{}…", &digits[..keep])
}

fn terminate(child: &mut Child, label: &str) -> Result<()> {
    match child.try_wait()? {
        Some(_) => Ok(()),
        None => {
            child
                .kill()
                .with_context(|| format!("failed to kill {label}"))?;
            child.wait().ok();
            Ok(())
        }
    }
}
