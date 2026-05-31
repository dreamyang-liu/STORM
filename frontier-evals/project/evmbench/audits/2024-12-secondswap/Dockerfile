FROM evmbench/base

RUN git clone --recurse https://github.com/evmbench-org/2024-12-secondswap.git $AUDIT_DIR

WORKDIR $AUDIT_DIR

RUN npm i
RUN forge install
RUN forge build

WORKDIR $AGENT_DIR
