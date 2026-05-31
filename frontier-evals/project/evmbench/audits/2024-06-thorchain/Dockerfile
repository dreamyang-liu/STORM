FROM evmbench/base

RUN git clone --recurse https://github.com/evmbench-org/2024-06-thorchain.git $AUDIT_DIR

COPY ethereum/hardhat.config.js $AUDIT_DIR/ethereum/hardhat.config.js
COPY avalanche/hardhat.config.js $AUDIT_DIR/avalanche/hardhat.config.ts

# Ethereum Hardhat tests
WORKDIR $AUDIT_DIR/ethereum
RUN npm install --legacy-peer-deps
RUN npx hardhat clean
RUN npx hardhat compile
RUN npx hardhat test

# Avalanche Hardhat tests
WORKDIR $AUDIT_DIR/avalanche
RUN npm install --legacy-peer-deps
RUN npx hardhat clean
RUN npx hardhat compile
RUN npx hardhat test

WORKDIR $AGENT_DIR
