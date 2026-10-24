import pytest

from config.settings import Settings, require_livekit_credentials


def test_settings_have_safe_defaults_without_development_credentials():
    settings = Settings.from_environment({})
    assert settings.LIVEKIT_URL == ""
    assert settings.LIVEKIT_API_KEY == ""
    assert settings.LIVEKIT_API_SECRET == ""
    assert settings.DEBUG is False
    assert settings.HOST == "127.0.0.1"


def test_livekit_worker_requires_explicit_credentials():
    settings = Settings.from_environment({})
    with pytest.raises(RuntimeError, match="LIVEKIT_URL") as error:
        require_livekit_credentials(settings)
    assert "LIVEKIT_API_SECRET" in str(error.value)


def test_livekit_worker_accepts_explicit_credentials():
    settings = Settings.from_environment({
        "LIVEKIT_URL": "wss://example.invalid",
        "LIVEKIT_API_KEY": "key-test",
        "LIVEKIT_API_SECRET": "secret-test",
    })
    require_livekit_credentials(settings)


def test_invalid_debug_and_ports_fail_clearly():
    with pytest.raises(ValueError, match="DEBUG"):
        Settings.from_environment({"DEBUG": "maybe"})
    with pytest.raises(ValueError, match="PORT"):
        Settings.from_environment({"PORT": "70000"})
