FROM evmbench/base:latest

RUN git clone --recurse https://github.com/evmbench-org/2024-06-size.git $AUDIT_DIR

WORKDIR $AUDIT_DIR

RUN foundryup --install v0.3.0
RUN forge install
RUN forge build
# NOTE: the invariant fuzz test can take ~10 minutes to run
RUN forge test -vv --no-match-test invariant

WORKDIR $AGENT_DIR
