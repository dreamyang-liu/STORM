# `veto-core`

Core runtime for the Veto JSON-RPC proxy.

## Features

- **Runtime** – [`run`] bootstraps the Axum server, binds to the requested socket, and awaits Ctrl+C for shutdown
- **Proxy Engine** – [`router`] wires handlers around [`AppState`] so the proxy can forward or block JSON-RPC calls
- **JSON-RPC Validation** – strict parsing guards against malformed payloads and rejects batch requests up front
- **Error Reporting** – deterministic error payloads and rich [`ProxyError`] diagnostics for callers

## Usage

```rust,no_run
use veto_config::{resolve_config, Overrides};
use veto_core::run;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let config = resolve_config(None, Overrides::default())?;
    run(config).await?;
    Ok(())
}
```
