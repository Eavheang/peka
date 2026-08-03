from app.config import Settings


def test_settings_include_llama_connection():
    settings = Settings(
        _env_file=None,
        jwt_secret_key="test-only-secret-that-is-at-least-32-chars",
        llama_api_key="local-test-key",
    )

    assert settings.llama_base_url == "http://localhost:8080/v1"
    assert settings.llama_api_key.get_secret_value() == "local-test-key"
