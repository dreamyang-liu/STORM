FROM evmbench/base:latest

RUN git clone --recurse https://github.com/evmbench-org/2024-01-renft.git $AUDIT_DIR

WORKDIR $AUDIT_DIR/smart-contracts

RUN forge install
RUN forge test -vv

WORKDIR $AGENT_DIR
