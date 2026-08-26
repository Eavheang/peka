from app.config import Settings


def test_settings_include_llm_connection():
    settings = Settings(
        _env_file=None,
        jwt_secret_key="test-only-secret-that-is-at-least-32-chars",
        llm_base_url="https://example.test/v1",
        llm_api_key="local-test-key",
        llm_model="test-model",
    )

    assert settings.llm_base_url == "https://example.test/v1"
    assert settings.llm_api_key.get_secret_value() == "local-test-key"
    assert settings.llm_model == "test-model"
