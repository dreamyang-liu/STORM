//! Exec-txs command implementation.
//!
//! Re-executes a list of transactions against the configured chain.

use anyhow::Result;
use clap::Args;
use ploit_exec::{Executor, LocalExecutor, LocalExecutorConfig};
use std::path::PathBuf;

/// Arguments for the exec-txs command
#[derive(Debug, Args)]
pub(crate) struct ExecTxsArgs {
    /// Input file containing transaction list (JSON)
    #[clap(short, long)]
    input: PathBuf,

    /// Tells the executor to use the gold wallet.
    #[clap(short, long, default_value_t = false)]
    gold: bool,

    /// Enables retrying failed transaction re-executions.
    #[clap(long = "enable-retries", default_value_t = false)]
    enable_retries: bool,

    /// Timeout (in seconds) for retrying failed re-executions.
    #[clap(
        long = "retry-timeout",
        default_value_t = LocalExecutorConfig::DEFAULT_RETRY_TIMEOUT_SECS,
        value_parser = clap::value_parser!(u64).range(1..)
    )]
    retry_timeout: u64,

    /// Configuration file (optional)
    #[clap(short, long, default_value = ".ploit.toml")]
    config: PathBuf,
}

impl ExecTxsArgs {
    /// Runs the exec-txs command.
    pub(crate) async fn run(self) -> Result<()> {
        let config = LocalExecutorConfig::new(
            self.input,
            self.config,
            self.gold,
            self.enable_retries,
            self.retry_timeout,
        );
        LocalExecutor::from(config).execute().await
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use clap::Parser;

    #[derive(Debug, Parser)]
    struct TestCli {
        #[clap(subcommand)]
        command: TestCommand,
    }

    #[derive(Debug, clap::Subcommand)]
    enum TestCommand {
        ExecTxs(ExecTxsArgs),
    }

    #[test]
    fn test_exec_txs_args_parsing() {
        let args = vec!["test", "exec-txs", "--input", "txs.json"];
        let cli = TestCli::try_parse_from(args).unwrap();

        let TestCommand::ExecTxs(exec_args) = cli.command;
        assert_eq!(exec_args.input, PathBuf::from("txs.json"));
        assert!(!exec_args.enable_retries);
        assert_eq!(
            exec_args.retry_timeout,
            LocalExecutorConfig::DEFAULT_RETRY_TIMEOUT_SECS
        );
    }

    #[test]
    fn test_exec_txs_with_custom_config() {
        let args = vec![
            "test",
            "exec-txs",
            "-i",
            "txs.json",
            "-c",
            "custom.toml",
            "--enable-retries",
            "--retry-timeout",
            "120",
        ];
        let cli = TestCli::try_parse_from(args).unwrap();

        let TestCommand::ExecTxs(exec_args) = cli.command;
        assert_eq!(exec_args.input, PathBuf::from("txs.json"));
        assert_eq!(exec_args.config, PathBuf::from("custom.toml"));
        assert!(exec_args.enable_retries);
        assert_eq!(exec_args.retry_timeout, 120);
    }

    #[test]
    fn test_exec_txs_default_config() {
        let args = vec!["test", "exec-txs", "--input", "txs.json"];
        let cli = TestCli::try_parse_from(args).unwrap();

        let TestCommand::ExecTxs(exec_args) = cli.command;
        assert_eq!(exec_args.config, PathBuf::from(".ploit.toml"));
        assert_eq!(
            exec_args.retry_timeout,
            LocalExecutorConfig::DEFAULT_RETRY_TIMEOUT_SECS
        );
    }
}
