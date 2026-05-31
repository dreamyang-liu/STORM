//! Kill command implementation.
//!
//! The kill command terminates the process occupying the configured chain port.
//! Works on both macOS and Windows.

use anyhow::Result;
use clap::Args;
use ploit_utils::{KillConfig, KillService};
use std::path::PathBuf;

/// Arguments for the kill command
#[derive(Debug, Args)]
pub(crate) struct KillArgs {
    /// Configuration file to read the port from
    #[clap(short, long, default_value = ".ploit.toml")]
    config: PathBuf,

    /// Port to kill (overrides config)
    #[clap(short, long)]
    port: Option<u16>,
}

impl KillArgs {
    /// Runs the kill command.
    pub(crate) async fn run(self) -> Result<()> {
        let config = KillConfig::new(self.config, self.port)?;
        KillService::from(config).kill().await
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
        Kill(KillArgs),
    }

    #[test]
    fn test_kill_args_defaults() {
        let args = vec!["test", "kill"];
        let cli = TestCli::try_parse_from(args).unwrap();

        let TestCommand::Kill(kill_args) = cli.command;
        assert_eq!(kill_args.config, PathBuf::from(".ploit.toml"));
        assert_eq!(kill_args.port, None);
    }

    #[test]
    fn test_kill_with_port() {
        let args = vec!["test", "kill", "--port", "8545"];
        let cli = TestCli::try_parse_from(args).unwrap();

        let TestCommand::Kill(kill_args) = cli.command;
        assert_eq!(kill_args.port, Some(8545));
    }

    #[test]
    fn test_kill_with_config() {
        let args = vec!["test", "kill", "--config", "custom.toml"];
        let cli = TestCli::try_parse_from(args).unwrap();

        let TestCommand::Kill(kill_args) = cli.command;
        assert_eq!(kill_args.config, PathBuf::from("custom.toml"));
    }
}
