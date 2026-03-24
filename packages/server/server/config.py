from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    store_path: str = "./backtest_catalog"
    cors_origins: list[str] = ["http://localhost:5173"]

    model_config = {"env_prefix": "NAUTILUS_"}


def get_settings() -> Settings:
    return Settings()
