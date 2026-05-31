FROM evmbench/base

RUN git clone --recurse https://github.com/evmbench-org/2025-02-thorwallet.git $AUDIT_DIR

WORKDIR $AUDIT_DIR

RUN npm install
RUN npx hardhat compile
RUN npx hardhat test

WORKDIR $AGENT_DIR
