FROM evmbench/base:latest

RUN git clone --recurse https://github.com/evmbench-org/2026-01-tempo-stablecoin-dex.git $AUDIT_DIR

WORKDIR $AUDIT_DIR

RUN forge install
RUN forge build
RUN forge test -vv
RUN forge clean

WORKDIR $AGENT_DIR
