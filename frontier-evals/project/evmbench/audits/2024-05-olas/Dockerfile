FROM evmbench/base:latest

RUN git clone --recurse https://github.com/evmbench-org/2024-05-olas.git $AUDIT_DIR

RUN apt-get update && apt-get install -y \
    libusb-1.0-0-dev \
    libudev-dev \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash && \
    export NVM_DIR="$HOME/.nvm" && \
    . "$NVM_DIR/nvm.sh" && \
    nvm install 18 && \
    nvm alias default 18 && \
    nvm use 18 && \
    node -v

RUN . "$HOME/.nvm/nvm.sh" && npm install -g yarn

WORKDIR $AUDIT_DIR/tokenomics

RUN . "$HOME/.nvm/nvm.sh" && yarn install
RUN . "$HOME/.nvm/nvm.sh" && npx hardhat compile

WORKDIR $AUDIT_DIR/registries

RUN . "$HOME/.nvm/nvm.sh" && yarn install
RUN . "$HOME/.nvm/nvm.sh" && npx hardhat test || true

WORKDIR $AUDIT_DIR/governance

RUN . "$HOME/.nvm/nvm.sh" && yarn install
RUN . "$HOME/.nvm/nvm.sh" && npx hardhat test || true 

WORKDIR $AGENT_DIR
