import os
from pathlib import Path


def prepare_bedrock_container_auth() -> tuple[list[str], list[str]]:
    """Expose AWS config to agent-server without putting secret values in logs."""
    forward_env = [
        "AWS_SHARED_CREDENTIALS_FILE",
        "AWS_CONFIG_FILE",
        "AWS_PROFILE",
        "AWS_REGION_NAME",
        "AWS_REGION",
        "AWS_DEFAULT_REGION",
        "AWS_EC2_METADATA_DISABLED",
    ]
    volumes: list[str] = []

    region = (
        os.getenv("AWS_REGION_NAME")
        or os.getenv("AWS_REGION")
        or os.getenv("AWS_DEFAULT_REGION")
    )
    if region:
        os.environ.setdefault("AWS_DEFAULT_REGION", region)

    os.environ.setdefault("AWS_EC2_METADATA_DISABLED", "true")

    aws_files = (
        ("AWS_SHARED_CREDENTIALS_FILE", Path.home() / ".aws" / "credentials"),
        ("AWS_CONFIG_FILE", Path.home() / ".aws" / "config"),
    )
    for env_name, default_path in aws_files:
        configured_path = os.getenv(env_name)
        source_path = Path(configured_path).expanduser() if configured_path else default_path
        if not source_path.is_file():
            continue

        resolved_path = source_path.resolve()
        os.environ[env_name] = str(resolved_path)
        volumes.append(f"{resolved_path}:{resolved_path}:ro")

    return forward_env, volumes
