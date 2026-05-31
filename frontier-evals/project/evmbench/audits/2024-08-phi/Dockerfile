FROM evmbench/base:latest

RUN curl -fsSl https://bun.sh/install | bash && \
    export BUN_INSTALL="$HOME/.bun" && \
    export PATH="$BUN_INSTALL/bin:$PATH" && \
    echo 'export BUN_INSTALL="$HOME/.bun"' >> ~/.bashrc && \
    echo 'export PATH="$BUN_INSTALL/bin:$PATH"' >> ~/.bashrc

RUN git clone --recurse https://github.com/evmbench-org/2024-08-phi $AUDIT_DIR

WORKDIR $AUDIT_DIR

RUN git submodule update --init --recursive
RUN . ~/.bashrc && bun install
RUN forge build
RUN forge test -vvv

WORKDIR $AGENT_DIR