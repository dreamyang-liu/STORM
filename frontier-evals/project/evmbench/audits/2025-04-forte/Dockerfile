FROM evmbench/base

RUN git clone --recurse https://github.com/evmbench-org/2025-04-forte.git $AUDIT_DIR

WORKDIR $AUDIT_DIR

RUN pip install -r requirements.txt
RUN forge install
RUN forge build
RUN forge test --ffi

WORKDIR $AGENT_DIR
