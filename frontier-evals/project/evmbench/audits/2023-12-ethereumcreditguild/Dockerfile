FROM evmbench/base:latest

RUN git clone --recurse https://github.com/evmbench-org/2023-12-ethereumcreditguild.git $AUDIT_DIR

RUN apt-get update && apt-get install -y \
    libusb-1.0-0-dev \
    libudev-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR $AUDIT_DIR

RUN foundryup --install nightly-5b7e4cb3c882b28f3c32ba580de27ce7381f415a

RUN npm install
RUN npm run test

WORKDIR $AGENT_DIR
