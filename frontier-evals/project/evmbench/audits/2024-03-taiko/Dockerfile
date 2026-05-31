FROM evmbench/base:latest

RUN git clone --recurse https://github.com/evmbench-org/2024-03-taiko.git $AUDIT_DIR

RUN corepack enable && corepack prepare pnpm@latest --activate
RUN foundryup --install nightly-de33b6af53005037b463318d2628b5cfcaf39916

WORKDIR $AUDIT_DIR/packages/protocol

RUN pnpm install

COPY replace_symlinks_with_real_files.sh $AUDIT_DIR/packages/protocol/
RUN ./replace_symlinks_with_real_files.sh
RUN rm replace_symlinks_with_real_files.sh

RUN pnpm compile
RUN forge test --json

WORKDIR $AGENT_DIR