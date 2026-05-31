FROM evmbench/base:latest

RUN git clone --recurse https://github.com/evmbench-org/2024-07-benddao.git $AUDIT_DIR

RUN npm install -g yarn
RUN npm install -g typescript --dev

WORKDIR $AUDIT_DIR

RUN yarn
RUN foundryup --install v0.3.0

RUN forge install
RUN forge build
RUN forge test -vvv

WORKDIR $AGENT_DIR
