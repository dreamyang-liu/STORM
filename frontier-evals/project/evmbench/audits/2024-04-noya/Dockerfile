FROM evmbench/base:latest

RUN git clone --recurse https://github.com/evmbench-org/2024-04-noya.git $AUDIT_DIR

RUN apt-get update && apt-get install -y \
    libusb-1.0-0-dev \
    libudev-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR $AUDIT_DIR

RUN npm install --force
RUN npx hardhat compile
RUN forge install && forge test --match-contract "(H08FlashLoanExploit|BaseConnector|TestFlashLoan|TestAccounting)" -vvv --fuzz-seed 0

WORKDIR $AGENT_DIR
