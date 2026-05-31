<h1 align="center">
  <img src="../../assets/logo.png" alt="veto banner placeholder" width="35%" align="center">
</h1>

<h4 align="center">
  Minimal, robust JSON-RPC gatekeeper for Anvil and other Ethereum dev nodes.
</h4>

<p align="center">
  <em>Targeted safeguards for local testing flows that cannot afford unsafe RPC calls.</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Rust-1.88+-orange.svg?labelColor=2a2f35" alt="Rust">
</p>

<p align="center">
  <a href="#installation">Installation</a> •
  <a href="#configuration">Configuration</a> •
  <a href="#features">Features</a> •
  <a href="#docker">Docker</a> •
  <a href="#usage">Usage</a> •
  <a href="#why">Why?</a> •
  <a href="#contributing">Contributing</a>
</p>

### Features

- Deterministic JSON-RPC filtering with lowercase method matching and batch rejection.
- Fast proxy built on Axum that forwards permissible payloads untouched to the upstream node.
- TOML + CLI configuration merger with sensible defaults for bind address and upstream URL.
- Structured tracing with INFO/WARN/ERROR logs for start-up, blocked calls, and shutdown events.

### Installation

> NOTE: `veto` is built from source in this workspace. Use the commands below to
> build or install locally.

```sh
# Install the workspace binary while developing locally.
cargo install --path bin/veto

# Build a release binary directly when you need artifacts.
cargo build --release -p veto
```

`veto` targets Rust `1.88+` and ships with comprehensive tests. Run `cargo test` in the workspace to validate a local build.

### Configuration

`veto` reads configuration from a TOML file (defaults to `.veto.toml`) and merges it with CLI overrides. Defaults resolve to `0.0.0.0:8546` for the bind address and `http://127.0.0.1:8545` for the upstream. Out of the box it blocks every documented `anvil_*` helper together with Hardhat/Ganache `evm_*` methods. All method names are normalized to lowercase before being enforced, and duplicate entries collapse automatically.

```toml
# .veto.toml
bind_address = "0.0.0.0:8546"
upstream_url = "http://127.0.0.1:8545"

blocked_methods = [
  "anvil_setBalance",
  "anvil_setNonce",
  "evm_increaseTime",
  "eth_sendTransaction"
]
```

> TIP
>
> You can provide the same values at runtime with flags such as `--bind-address`, `--upstream-url`, or `--blocked-methods eth_sendtransaction,personal_sign`. CLI flags always take precedence over file values.

The proxy refuses batch JSON-RPC requests and responds with a JSON-RPC error payload when a blocked method is invoked.

### Docker

A multi-stage `Dockerfile` is included for building slim runtime images. Build the
builder image locally:

```sh
# Build the minimal scratch-based builder image containing /veto.
just docker-build
```

The resulting `veto-builder` stage only ships the compiled binary, making it ideal
for copy-paste into bespoke runtime images:

```dockerfile
FROM veto-builder:latest AS veto

FROM debian:bookworm-slim
COPY --from=veto /veto /usr/local/bin/veto
ENTRYPOINT ["/usr/local/bin/veto"]
```

### Usage

Launch the proxy after you have an upstream Anvil (or any Ethereum JSON-RPC) node running:

```sh
# start anvil in another terminal
anvil --port 8545

# run veto in front of it
veto \
  --bind-address 127.0.0.1:8546 \
  --upstream-url http://127.0.0.1:8545 \
  --blocked-methods anvil_setbalance,eth_sendtransaction
```

Send RPC traffic to `http://127.0.0.1:8546` (or the bind address you configure). Any blocked method receives a deterministic JSON-RPC error response and the event is logged:

```sh
curl -s -X POST http://127.0.0.1:8546 \
  -H "content-type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"eth_sendTransaction","params":[]}'

# -> { "jsonrpc":"2.0", "error":{ "code":-32601, "message":"Method 'eth_sendTransaction' blocked by veto proxy" }, "id":1 }
```

All other payloads are forwarded untouched to the upstream node.

### Why?

Smart contract testing frequently requires unsafe JSON-RPC helpers (e.g. `anvil_setBalance`, `evm_setNextBlockTimestamp`) that must never leak into higher-stakes environments. `veto` provides:

- A focused allow/deny layer that sits in front of local Anvil or Hardhat instances.
- Hard default blocking lists you can codify per project to de-risk automation.
- Clear audit trails via structured logging so you know when and why a call was denied.

The proxy keeps development workflows flexible while enforcing the guardrails needed for repeatable evaluation setups, CI pipelines, and shared testing infrastructure.
