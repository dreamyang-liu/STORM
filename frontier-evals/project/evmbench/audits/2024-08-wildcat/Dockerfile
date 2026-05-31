FROM evmbench/base:latest

RUN git clone --recurse https://github.com/evmbench-org/2024-08-wildcat.git $AUDIT_DIR
RUN foundryup --install v0.3.0

WORKDIR $AUDIT_DIR

RUN forge install
RUN forge build
RUN forge test -vvv

WORKDIR $AGENT_DIR
