def test_app_uses_declared_settings_contract():
    from api.app.main import app

    assert app.title == "Mix Analyst"
    assert app.openapi_url == "/api/v1/openapi.json"


def test_compose_storage_alias_is_applied(monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", "/storage")

    from api.app.config import Settings

    assert Settings().storage_root == "/storage"
