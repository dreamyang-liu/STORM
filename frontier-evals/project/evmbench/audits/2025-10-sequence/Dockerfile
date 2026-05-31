FROM evmbench/base:latest

RUN git clone --recurse https://github.com/evmbench-org/2025-10-sequence.git $AUDIT_DIR

WORKDIR $AUDIT_DIR

RUN forge install
RUN forge build

WORKDIR $AGENT_DIR