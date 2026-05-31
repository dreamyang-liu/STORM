# `ploit-config`

Configuration management for ploit evaluation environments.

## Features

- **Configuration Types** - [`PloitConfig`] and [`DeployedContract`] for storing setup state and deployed contracts
- **File I/O** - Load and save configurations from TOML files
- **Config Manager** - [`ConfigManager`], [`ConfigKey`], [`ConfigAction`], and [`ActionType`] for managing configuration values via CLI
- **Constants** - Default values for RPC ports, wallet addresses, and file paths

## Usage

```rust
use ploit_config::PloitConfig;
use std::path::Path;

// Load configuration from file
let config = PloitConfig::load_from(Path::new(".ploit.toml"))?;

// Load or use default if file doesn't exist
let config = PloitConfig::load_or_default(Path::new(".ploit.toml"))?;

// Use default configuration
let config = PloitConfig::default();

// Save configuration
config.save_to(Path::new(".ploit.toml"))?;
```
