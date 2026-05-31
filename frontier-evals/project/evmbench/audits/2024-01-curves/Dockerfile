FROM evmbench/base:latest

RUN git clone --recurse https://github.com/evmbench-org/2024-01-curves.git $AUDIT_DIR

RUN apt-get update && apt-get install -y \
    libusb-1.0-0-dev \
    libudev-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR $AUDIT_DIR

RUN npm install --force
RUN npx hardhat compile
RUN npx hardhat test

WORKDIR $AGENT_DIR
