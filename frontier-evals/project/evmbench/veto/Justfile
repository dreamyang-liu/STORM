set positional-arguments

alias t := test
alias l := lint
alias f := fmt-fix
alias c := check
alias b := build
alias h := hack
alias e := examples
alias z := zepter
alias u := check-udeps

# Default recipe to display available commands.
default:
  @just --list

# Run the full suite of formatting, linting, and tests used in CI.
ci:
  @just fmt-fix
  @just fmt-check
  @just lint-docs
  @just hack
  @just zepter
  @just check-udeps
  @just test

# Run the full test suite (excludes online tests by default).
test *args="-E '!test(test_online)'":
  cargo nextest run --workspace --all-features {{args}}

# Run all linting commands (formatting, docs, and clippy).
lint *args='':
  @just fmt-fix
  @just fmt-check
  @just lint-docs
  @just clippy {{args}}

# Run clippy with warnings treated as errors.
clippy *args='':
  cargo clippy --workspace --all-targets --all-features -- -D warnings {{args}}

# Run stable cargo fmt across the workspace.
fmt:
  cargo fmt --all

# Run nightly cargo fmt and apply fixes.
fmt-fix:
  cargo +nightly fmt --all

# Run nightly cargo fmt in check-only mode.
fmt-check:
  cargo +nightly fmt --all -- --check

# Run clippy checks for the workspace with customizable args.
check *args="--all-features":
  cargo clippy --workspace {{args}}

# Build the entire workspace, defaulting to release with all features.
build *args='--release --all-features':
  cargo build --workspace {{args}}

# Run the veto binary with optional CLI args.
run *args='':
  cargo run --package veto -- {{args}}

# Build the Docker builder image for veto.
docker-build:
  docker build -t veto-builder:latest --target veto-builder .

# Run veto using the binary name directly.
veto *args:
  cargo run --bin veto -- {{args}}

# Build documentation with warnings promoted to errors.
lint-docs:
  RUSTDOCFLAGS="-D warnings" cargo doc --workspace --no-deps --document-private-items

# Run cargo hack to check the full feature matrix.
hack:
  cargo hack check --feature-powerset --no-dev-deps

# Build all example binaries.
examples-build:
  cargo check --package anvil-veto-blocklist
  cargo check --package anvil-veto-allow-all

# Run all example binaries.
examples:
  just examples-build
  cargo run --package anvil-veto-blocklist
  cargo run --package anvil-veto-allow-all

# Check for unused dependencies in the workspace.
check-udeps:
  cargo +nightly udeps --workspace --all-features --all-targets

# Ensure zepter is installed and run formatting plus linting.
zepter:
  #!/usr/bin/env bash
  set -euo pipefail
  if ! command -v zepter &> /dev/null; then
    echo "Installing zepter..."
    cargo install zepter -f --locked
  fi
  zepter --version
  zepter format features
  zepter

# Ensure zepter is installed and fix formatting issues.
zepter-fix:
  #!/usr/bin/env bash
  set -euo pipefail
  if ! command -v zepter &> /dev/null; then
    echo "Installing zepter..."
    cargo install zepter -f --locked
  fi
  zepter --version
  zepter format features --fix
  zepter
