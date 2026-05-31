FROM evmbench/base:latest

RUN git clone --recurse https://github.com/evmbench-org/2025-01-liquid-ron.git $AUDIT_DIR

WORKDIR $AUDIT_DIR
RUN forge install
RUN forge build
RUN forge test -vvv

WORKDIR $AGENT_DIR
