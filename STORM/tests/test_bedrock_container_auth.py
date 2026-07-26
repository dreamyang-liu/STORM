import os
from pathlib import Path

from core.bedrock import prepare_bedrock_container_auth


def test_bedrock_credentials_are_mounted_without_forwarding_secret_values(
    monkeypatch, tmp_path
):
    credentials_file = tmp_path / "credentials"
    credentials_file.write_text(
        "[default]\naws_access_key_id = test\naws_secret_access_key = test\n"
    )

    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", str(credentials_file))
    monkeypatch.setenv("AWS_REGION_NAME", "us-west-2")
    monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    monkeypatch.delenv("AWS_SESSION_TOKEN", raising=False)

    forward_env, volumes = prepare_bedrock_container_auth()

    resolved_path = str(Path(credentials_file).resolve())
    assert f"{resolved_path}:{resolved_path}:ro" in volumes
    assert "AWS_SHARED_CREDENTIALS_FILE" in forward_env
    assert "AWS_DEFAULT_REGION" in forward_env
    assert "AWS_ACCESS_KEY_ID" not in forward_env
    assert "AWS_SECRET_ACCESS_KEY" not in forward_env
    assert "AWS_SESSION_TOKEN" not in forward_env
    assert os.environ["AWS_DEFAULT_REGION"] == "us-west-2"
    assert os.environ["AWS_EC2_METADATA_DISABLED"] == "true"
