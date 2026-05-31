FROM evmbench:base/latest

RUN git clone --recurse <REPO_URL> $CODEBASE_DIR

WORKDIR $AUDIT_DIR

# Install dependencies
# Ensure that tests can run

WORKDIR $AGENT_DIR
