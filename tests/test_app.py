from app import create_app


def test_health_endpoint_returns_ok():
    app = create_app()
    client = app.test_client()

    response = client.get("/health")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "healthy"


def test_home_includes_environment(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "staging")
    app = create_app()
    client = app.test_client()

    response = client.get("/")

    assert response.status_code == 200
    assert "staging" in response.get_data(as_text=True)


def test_env_configuration_overrides_defaults(monkeypatch):
    monkeypatch.setenv("APP_PORT", "7777")
    monkeypatch.setenv("APP_NAME", "unit-test-app")
    app = create_app()

    assert app.config["APP_PORT"] == 7777
    assert app.config["APP_NAME"] == "unit-test-app"
