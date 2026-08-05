from unittest.mock import MagicMock, patch

import pytest

import continuum.db as db_module


@pytest.fixture(autouse=True)
def _reset_cache():
    db_module._cached_database_url = None
    yield
    db_module._cached_database_url = None


def test_prefers_database_url_env_var(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://direct-env-var")
    monkeypatch.delenv("COCKROACHDB_SECRET_ARN", raising=False)

    assert db_module._resolve_database_url() == "postgresql://direct-env-var"


def test_falls_back_to_secrets_manager(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("COCKROACHDB_SECRET_ARN", "arn:aws:secretsmanager:...:secret:foo")

    mock_client = MagicMock()
    mock_client.get_secret_value.return_value = {"SecretString": "postgresql://from-secret"}
    with patch("continuum.db.boto3.client", return_value=mock_client):
        result = db_module._resolve_database_url()

    assert result == "postgresql://from-secret"
    mock_client.get_secret_value.assert_called_once_with(
        SecretId="arn:aws:secretsmanager:...:secret:foo"
    )


def test_secret_is_fetched_once_and_cached(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("COCKROACHDB_SECRET_ARN", "arn:aws:secretsmanager:...:secret:foo")

    mock_client = MagicMock()
    mock_client.get_secret_value.return_value = {"SecretString": "postgresql://from-secret"}
    with patch("continuum.db.boto3.client", return_value=mock_client):
        db_module._resolve_database_url()
        db_module._resolve_database_url()

    mock_client.get_secret_value.assert_called_once()


def test_raises_when_neither_is_set(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("COCKROACHDB_SECRET_ARN", raising=False)

    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        db_module._resolve_database_url()
