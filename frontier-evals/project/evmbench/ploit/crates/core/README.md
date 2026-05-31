# `ploit-core`

Core functionality for environment setup, transaction loading, and address management in ploit.

## Features

- **Environment Setup** - [`Setup`] and [`SetupConfig`] for initializing test environments with anvil chain, wallet funding, and contract deployment
- **Transaction Loading** - [`TransactionLoader`] retrieves transaction history from the blockchain
- **Address Loading** - [`AddressLoader`] loads deployed contract addresses from configuration
- **Filtering** - Transaction filtering by status (success, failed, all) and limits
- **Display** - Table and JSON output formats for transactions and addresses

## Installation

This crate is part of the workspace and is not published separately. Use a
path dependency from the workspace root:

```toml
ploit-core = { path = "crates/core", default-features = false }
```

## Usage

```rust
use ploit_core::{TransactionLoader, AddressLoader};

// Load transactions from the blockchain
let loader = TransactionLoader::default();
let transactions = loader.load().await?;
transactions.print_table();

// Load deployed contract addresses
let address_loader = AddressLoader::default();
let addresses = address_loader.load()?;
addresses.print_json();
```
