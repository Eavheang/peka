from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "PEKA Service"
    debug: bool = False
    database_url: str = "postgresql://peka:peka_dev_password@localhost:5432/peka"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
