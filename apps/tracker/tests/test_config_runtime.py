from config import settings, validate_runtime_settings


def test_validate_runtime_settings_requires_encryption(monkeypatch):
    monkeypatch.setattr(settings, "encryption_secret", "")
    monkeypatch.setattr(settings, "encryption_key", "")

    try:
        validate_runtime_settings()
    except RuntimeError as error:
        assert "ENCRYPTION_SECRET or ENCRYPTION_KEY" in str(error)
    else:
        raise AssertionError("Expected runtime validation to fail without encryption settings")


def test_validate_runtime_settings_accepts_secret(monkeypatch):
    monkeypatch.setattr(settings, "encryption_secret", "super-secret")
    monkeypatch.setattr(settings, "encryption_key", "")

    validate_runtime_settings()
