from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "YourNews"
    app_env: str = "development"
    database_url: str = "postgresql+psycopg2://yournews:yournews@postgres:5432/yournews"
    app_base_url: str = "http://127.0.0.1:8000"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
