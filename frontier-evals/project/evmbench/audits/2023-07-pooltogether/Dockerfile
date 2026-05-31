FROM evmbench/base:latest

RUN git clone --recurse https://github.com/evmbench-org/2023-07-pooltogether.git $AUDIT_DIR

WORKDIR $AUDIT_DIR/vault

RUN foundryup --install nightly-d369d2486f85576eec4ca41d277391dfdae21ba7

RUN forge install
RUN forge build
RUN forge test -vvv

WORKDIR $AGENT_DIR
