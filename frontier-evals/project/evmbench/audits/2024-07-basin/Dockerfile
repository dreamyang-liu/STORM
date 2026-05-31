FROM evmbench/base:latest

RUN git clone --recurse https://github.com/evmbench-org/2024-07-basin.git $AUDIT_DIR

RUN foundryup --install nightly-26a7559758c192911dd39ce7d621a18ef0d419e6

WORKDIR $AUDIT_DIR

RUN pip install -r requirements.txt
RUN forge build
RUN forge test --ffi -vv

WORKDIR $AGENT_DIR
