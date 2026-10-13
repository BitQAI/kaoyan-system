def test_settings_env_override(monkeypatch):
    monkeypatch.setenv("KY_DB_PATH", "/tmp/x.db")
    monkeypatch.setenv("AI_PROVIDER", "bailian")
    from app.config import get_settings

    get_settings.cache_clear()
    s = get_settings()
    assert s.db_path == "/tmp/x.db"
    assert s.ai_provider == "bailian"
    get_settings.cache_clear()


def test_settings_defaults():
    from app.config import get_settings

    get_settings.cache_clear()
    s = get_settings()
    assert s.token_days == 90
    assert s.opencode_base.startswith("https://opencode.ai/")
    get_settings.cache_clear()
