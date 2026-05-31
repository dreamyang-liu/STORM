# `ploit-utils`

Common utilities and helpers for the ploit workspace.

## Features

- **Backtrace** - Helper to enable Rust backtraces for debugging
- **Logging** - Structured logging utilities for consistent output
- **Signal Handlers** - SIGSEGV handler for crash diagnostics
- **CLI Styles** - Consistent styling for command-line interfaces
- **Process Management** - [`KillService`], [`KillConfig`], and `kill_port` for port killing and process utilities

## Usage

```rust
use ploit_utils::{backtrace, logging, styles, kill_port};

// Enable backtrace for debugging
backtrace::install();

// Initialize logging
logging::init(true); // verbose mode

// Kill a process on a specific port
kill_port(8545)?;

// Use CLI styles for consistent output
use styles::*;
println!("{}", SUCCESS.paint("Operation completed"));
```
