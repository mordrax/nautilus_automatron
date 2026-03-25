from pathlib import Path

from pydantic_settings import BaseSettings

_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    store_path: str = "./backtest_catalog"
    cors_origins: list[str] = ["http://localhost:5173"]
    port: int = 8000

    model_config = {
        "env_prefix": "NAUTILUS_",
        "env_file": str(_ENV_FILE) if _ENV_FILE.exists() else None,
        "extra": "ignore",
    }


def get_settings() -> Settings:
    return Settings()
