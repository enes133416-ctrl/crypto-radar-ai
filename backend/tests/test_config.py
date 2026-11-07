from app.config.settings import load_settings


def test_defaults():
    s = load_settings({})
    assert s.run_mode == "local"
    assert s.demo_mode is False
    assert "http://localhost:5173" in s.cors_origins


def test_env_override():
    s = load_settings({"RUN_MODE": "cloud", "DEMO_MODE": "true", "CORS_ORIGINS": "https://a.com, https://b.com", "MIN_QUOTE_VOLUME_24H": "123"})
    assert s.run_mode == "cloud" and s.demo_mode is True
    assert s.cors_origins == ("https://a.com", "https://b.com")
    assert s.min_quote_volume_24h == 123.0
