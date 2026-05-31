# Builder stage - creates the ploit binary
FROM rust:1.88-slim AS builder

WORKDIR /build

# Install dependencies
RUN apt-get update && apt-get install -y \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy ploit workspace files (build context is expected to be the evmbench repo root)
COPY ploit/Cargo.toml ploit/Cargo.lock ./
COPY ploit/bin ./bin
COPY ploit/crates ./crates
COPY ploit/examples ./examples

# Build the release binary
RUN cargo build --release --bin ploit

# Build the veto CLI from the in-repo source
FROM rust:1.88-slim AS veto-cli

WORKDIR /veto-build

RUN apt-get update && apt-get install -y \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

COPY veto ./veto
WORKDIR /veto-build/veto
RUN cargo build --release -p veto

# Final builder image - contains only the binary
FROM scratch AS ploit-builder

COPY --from=builder /build/target/release/ploit /ploit
COPY --from=veto-cli /veto-build/veto/target/release/veto /usr/local/bin/veto

# Runtime example (optional) - shows how to use the builder
FROM debian:bookworm-slim AS runtime

RUN apt-get update && apt-get install -y \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ploit-builder /ploit /usr/local/bin/ploit
COPY --from=ploit-builder /usr/local/bin/veto /usr/local/bin/veto

ENTRYPOINT ["/usr/local/bin/ploit"]
