# Builder stage - creates the veto binary
FROM rust:1.88-slim AS builder

WORKDIR /build

# Install dependencies
RUN apt-get update && apt-get install -y \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy workspace files
COPY Cargo.toml Cargo.lock ./
COPY bin ./bin
COPY crates ./crates
COPY examples ./examples
COPY Justfile ./Justfile

# Build the release binary
RUN cargo build --release --bin veto

# Final builder image - contains only the binary
FROM scratch AS veto-builder

COPY --from=builder /build/target/release/veto /veto

# Runtime example (optional) - shows how to use the builder
FROM debian:bookworm-slim AS runtime

RUN apt-get update && apt-get install -y \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=veto-builder /veto /usr/local/bin/veto

ENTRYPOINT ["/usr/local/bin/veto"]
