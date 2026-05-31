//! Config command implementation.
//!
//! Manages configuration for the ploit environment, allowing users to set
//! configuration values using dot-notation for nested fields.

use anyhow::Result;
use clap::{Args, Subcommand};
use ploit_config::ActionType;
use ploit_config::ConfigAction;
use ploit_config::ConfigManager;
use std::path::PathBuf;

/// Arguments for the config command
#[derive(Debug, Args)]
pub(crate) struct ConfigArgs {
    #[clap(subcommand)]
    command: ConfigCommands,
}

impl ConfigArgs {
    /// Runs the config command.
    pub(crate) async fn run(&self) -> Result<()> {
        let action_type = self.command.action();
        let key = self.command.key().map(Into::into);
        let act = ConfigAction::new(action_type, key);
        ConfigManager::new(self.command.config_path())
            .act(act)
            .await
    }
}

/// Available config subcommands
#[derive(Debug, Subcommand)]
enum ConfigCommands {
    /// Set a configuration value
    Set(SetArgs),
    /// Get a configuration value
    Get(GetArgs),
}

impl ConfigCommands {
    /// Returns the action type for the command.
    fn action(&self) -> ActionType {
        match self {
            Self::Set(args) => ActionType::Set(args.value.clone()),
            Self::Get(_) => ActionType::Get,
        }
    }

    /// Returns the key for the command, if applicable.
    fn key(&self) -> Option<String> {
        match self {
            Self::Set(args) => Some(args.key.clone()),
            Self::Get(args) => args.key.clone(),
        }
    }

    /// Returns the config file path for the command.
    fn config_path(&self) -> PathBuf {
        match self {
            Self::Set(args) => args.config.clone(),
            Self::Get(args) => args.config.clone(),
        }
    }
}

/// Arguments for the set subcommand
#[derive(Debug, Args)]
struct SetArgs {
    /// Configuration key (e.g., wallet.address, chain.rpc_port)
    key: String,

    /// Configuration value
    value: String,

    /// Configuration file path
    #[clap(short, long, default_value = ".ploit.toml")]
    config: PathBuf,
}

/// Arguments for the get subcommand
#[derive(Debug, Args)]
struct GetArgs {
    /// Configuration key (e.g., wallet.address, chain.rpc_port). If not specified, shows entire config.
    key: Option<String>,

    /// Configuration file path
    #[clap(short, long, default_value = ".ploit.toml")]
    config: PathBuf,
}

#[cfg(test)]
mod tests {
    use super::*;
    use clap::Parser;
    use ploit_config::PloitConfig;
    use std::fs;
    use tempfile::TempDir;

    #[derive(Debug, Parser)]
    struct TestCli {
        #[clap(subcommand)]
        command: TestCommand,
    }

    #[derive(Debug, clap::Subcommand)]
    enum TestCommand {
        Config(ConfigArgs),
    }

    #[test]
    fn test_config_set_parsing() {
        let args = vec!["test", "config", "set", "wallet.address", "0x1234"];
        let cli = TestCli::try_parse_from(args);
        assert!(cli.is_ok());
    }

    #[tokio::test]
    async fn test_set_wallet_address() {
        use alloy_primitives::address;

        let temp_dir = TempDir::new().unwrap();
        let config_path = temp_dir.path().join("config.toml");

        let test_address = "0x1234567890123456789012345678901234567890";
        let args = ConfigArgs {
            command: ConfigCommands::Set(SetArgs {
                key: "wallet.address".to_string(),
                value: test_address.to_string(),
                config: config_path.clone(),
            }),
        };

        let result = args.run().await;
        if let Err(ref e) = result {
            eprintln!("Error: {:?}", e);
        }
        assert!(result.is_ok());

        // Verify the config was saved
        let config = PloitConfig::load_or_default(&config_path).unwrap();
        let expected_address = address!("1234567890123456789012345678901234567890");
        assert_eq!(config.agent_address, expected_address);
    }

    #[tokio::test]
    async fn test_set_chain_port() {
        let temp_dir = TempDir::new().unwrap();
        let config_path = temp_dir.path().join("config.toml");

        let args = ConfigArgs {
            command: ConfigCommands::Set(SetArgs {
                key: "chain.rpc_port".to_string(),
                value: "9999".to_string(),
                config: config_path.clone(),
            }),
        };

        let result = args.run().await;
        if let Err(ref e) = result {
            eprintln!("Error: {:?}", e);
        }
        assert!(result.is_ok());

        // Verify the config was saved
        let config_str = fs::read_to_string(&config_path).unwrap();
        let config: ploit_config::PloitConfig = toml::from_str(&config_str).unwrap();
        assert_eq!(config.anvil_port, 9999);
        assert!(config.rpc_url.contains(":9999"));
    }

    #[tokio::test]
    async fn test_set_chain_id() {
        let temp_dir = TempDir::new().unwrap();
        let config_path = temp_dir.path().join("config.toml");

        let args = ConfigArgs {
            command: ConfigCommands::Set(SetArgs {
                key: "chain.chain_id".to_string(),
                value: "4242".to_string(),
                config: config_path.clone(),
            }),
        };

        let result = args.run().await;
        if let Err(ref e) = result {
            eprintln!("Error: {:?}", e);
        }
        assert!(result.is_ok());

        let config = PloitConfig::load_or_default(&config_path).unwrap();
        assert_eq!(config.chain_id, Some(4242));
        assert_eq!(config.chain_id(), 4242);
    }

    #[tokio::test]
    async fn test_set_chain_genesis_timestamp() {
        let temp_dir = TempDir::new().unwrap();
        let config_path = temp_dir.path().join("config.toml");

        let args = ConfigArgs {
            command: ConfigCommands::Set(SetArgs {
                key: "chain.genesis_timestamp".to_string(),
                value: "1700000000".to_string(),
                config: config_path.clone(),
            }),
        };

        let result = args.run().await;
        if let Err(ref e) = result {
            eprintln!("Error: {:?}", e);
        }
        assert!(result.is_ok());

        let config = PloitConfig::load_or_default(&config_path).unwrap();
        assert_eq!(config.genesis_timestamp, Some(1_700_000_000));
    }

    #[tokio::test]
    async fn test_set_chain_block_time() {
        let temp_dir = TempDir::new().unwrap();
        let config_path = temp_dir.path().join("config.toml");

        let args = ConfigArgs {
            command: ConfigCommands::Set(SetArgs {
                key: "chain.block_time".to_string(),
                value: "12".to_string(),
                config: config_path.clone(),
            }),
        };

        let result = args.run().await;
        if let Err(ref e) = result {
            eprintln!("Error: {:?}", e);
        }
        assert!(result.is_ok());

        let config = PloitConfig::load_or_default(&config_path).unwrap();
        assert_eq!(config.block_time, Some(12));
    }

    #[tokio::test]
    async fn test_set_chain_mnemonic() {
        let temp_dir = TempDir::new().unwrap();
        let config_path = temp_dir.path().join("config.toml");

        let mnemonic = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu";
        let args = ConfigArgs {
            command: ConfigCommands::Set(SetArgs {
                key: "chain.mnemonic".to_string(),
                value: mnemonic.to_string(),
                config: config_path.clone(),
            }),
        };

        let result = args.run().await;
        if let Err(ref e) = result {
            eprintln!("Error: {:?}", e);
        }
        assert!(result.is_ok());

        let config = PloitConfig::load_or_default(&config_path).unwrap();
        assert_eq!(config.mnemonic, Some(mnemonic.to_string()));
        assert_eq!(config.mnemonic(), mnemonic);
    }

    #[tokio::test]
    async fn test_set_chain_mnemonic_empty() {
        let temp_dir = TempDir::new().unwrap();
        let config_path = temp_dir.path().join("config.toml");

        let args = ConfigArgs {
            command: ConfigCommands::Set(SetArgs {
                key: "chain.mnemonic".to_string(),
                value: "".to_string(),
                config: config_path,
            }),
        };

        let result = args.run().await;
        assert!(result.is_err());
    }

    #[tokio::test]
    async fn test_set_chain_gas_price() {
        let temp_dir = TempDir::new().unwrap();
        let config_path = temp_dir.path().join("config.toml");

        let args = ConfigArgs {
            command: ConfigCommands::Set(SetArgs {
                key: "chain.gas_price".to_string(),
                value: "42000000000".to_string(),
                config: config_path.clone(),
            }),
        };

        let result = args.run().await;
        if let Err(ref e) = result {
            eprintln!("Error: {:?}", e);
        }
        assert!(result.is_ok());

        let config = PloitConfig::load_or_default(&config_path).unwrap();
        assert_eq!(config.gas_price, Some(42_000_000_000));
    }

    #[tokio::test]
    async fn test_set_chain_block_base_fee_per_gas() {
        let temp_dir = TempDir::new().unwrap();
        let config_path = temp_dir.path().join("config.toml");

        let args = ConfigArgs {
            command: ConfigCommands::Set(SetArgs {
                key: "chain.block_base_fee_per_gas".to_string(),
                value: "1000000000".to_string(),
                config: config_path.clone(),
            }),
        };

        let result = args.run().await;
        if let Err(ref e) = result {
            eprintln!("Error: {:?}", e);
        }
        assert!(result.is_ok());

        let config = PloitConfig::load_or_default(&config_path).unwrap();
        assert_eq!(config.block_base_fee_per_gas, Some(1_000_000_000));
    }

    #[tokio::test]
    async fn test_set_chain_gas_limit() {
        let temp_dir = TempDir::new().unwrap();
        let config_path = temp_dir.path().join("config.toml");

        let args = ConfigArgs {
            command: ConfigCommands::Set(SetArgs {
                key: "chain.gas_limit".to_string(),
                value: "30000000".to_string(),
                config: config_path.clone(),
            }),
        };

        let result = args.run().await;
        if let Err(ref e) = result {
            eprintln!("Error: {:?}", e);
        }
        assert!(result.is_ok());

        let config = PloitConfig::load_or_default(&config_path).unwrap();
        assert_eq!(config.gas_limit, Some(30_000_000));
    }

    #[tokio::test]
    async fn test_invalid_key() {
        let temp_dir = TempDir::new().unwrap();
        let config_path = temp_dir.path().join("config.toml");

        let args = ConfigArgs {
            command: ConfigCommands::Set(SetArgs {
                key: "invalid.key".to_string(),
                value: "value".to_string(),
                config: config_path,
            }),
        };

        let result = args.run().await;
        assert!(result.is_err());
    }

    #[test]
    fn test_config_get_parsing() {
        let args = vec!["test", "config", "get", "wallet.address"];
        let cli = TestCli::try_parse_from(args);
        assert!(cli.is_ok());
    }

    #[tokio::test]
    async fn test_get_wallet_address() {
        let temp_dir = TempDir::new().unwrap();
        let config_path = temp_dir.path().join("config.toml");

        // First set a value
        let test_address = "0x1234567890123456789012345678901234567890";
        let set_args = ConfigArgs {
            command: ConfigCommands::Set(SetArgs {
                key: "wallet.address".to_string(),
                value: test_address.to_string(),
                config: config_path.clone(),
            }),
        };
        set_args.run().await.unwrap();

        // Now get it back
        let get_args = ConfigArgs {
            command: ConfigCommands::Get(GetArgs {
                key: Some("wallet.address".to_string()),
                config: config_path,
            }),
        };
        let result = get_args.run().await;
        assert!(result.is_ok());
    }

    #[tokio::test]
    async fn test_get_chain_rpc_port() {
        let temp_dir = TempDir::new().unwrap();
        let config_path = temp_dir.path().join("config.toml");

        // First set a value
        let set_args = ConfigArgs {
            command: ConfigCommands::Set(SetArgs {
                key: "chain.rpc_port".to_string(),
                value: "9999".to_string(),
                config: config_path.clone(),
            }),
        };
        set_args.run().await.unwrap();

        // Now get it back
        let get_args = ConfigArgs {
            command: ConfigCommands::Get(GetArgs {
                key: Some("chain.rpc_port".to_string()),
                config: config_path,
            }),
        };
        let result = get_args.run().await;
        assert!(result.is_ok());
    }

    #[tokio::test]
    async fn test_get_invalid_key() {
        let temp_dir = TempDir::new().unwrap();
        let config_path = temp_dir.path().join("config.toml");

        let args = ConfigArgs {
            command: ConfigCommands::Get(GetArgs {
                key: Some("invalid.key".to_string()),
                config: config_path,
            }),
        };

        let result = args.run().await;
        assert!(result.is_err());
    }

    #[tokio::test]
    async fn test_get_default_config() {
        let temp_dir = TempDir::new().unwrap();
        let config_path = temp_dir.path().join("nonexistent-config.toml");

        // Getting from a non-existent config should use defaults
        let args = ConfigArgs {
            command: ConfigCommands::Get(GetArgs {
                key: Some("chain.rpc_port".to_string()),
                config: config_path,
            }),
        };
        let result = args.run().await;
        assert!(result.is_ok());
    }

    #[tokio::test]
    async fn test_get_whole_config() {
        let temp_dir = TempDir::new().unwrap();
        let config_path = temp_dir.path().join("config.toml");

        // Set a value first
        let set_args = ConfigArgs {
            command: ConfigCommands::Set(SetArgs {
                key: "chain.rpc_port".to_string(),
                value: "9999".to_string(),
                config: config_path.clone(),
            }),
        };
        set_args.run().await.unwrap();

        // Get whole config (no key specified)
        let args = ConfigArgs {
            command: ConfigCommands::Get(GetArgs {
                key: None,
                config: config_path,
            }),
        };
        let result = args.run().await;
        assert!(result.is_ok());
    }
}
