# `veto-config`

Configuration management for the Veto JSON-RPC proxy.

## Features

- **Configuration File** – [`FileConfig`] mirrors the on-disk `.veto.toml`
- **CLI Overrides** – [`Overrides`] captures runtime flags and environment tweaks
- **Resolution Pipeline** – [`resolve_config`] merges defaults, files, and overrides into a [`Config`]
- **Defaults** – [`DEFAULT_BIND_ADDRESS`], [`DEFAULT_UPSTREAM_URL`], [`DEFAULT_CONFIG_PATH`] centralize proxy constants
- **Normalization** – method names are trimmed, lowercased, and deduplicated before reaching the runtime

## Usage

```rust
# fn main() -> Result<(), Box<dyn std::error::Error>> {
use std::path::Path;
use veto_config::{load_file, resolve_config, Overrides};

let file = load_file(Path::new(".veto.toml"))?;
let overrides = Overrides::default();
let config = resolve_config(file, overrides)?;

println!("Proxy listening on {}", config.bind_address());
println!("Forwarding to {}", config.upstream_url());
# Ok(())
# }
```
