from pathlib import Path

from pydantic import AnyUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration read from environment variables or defaults."""

    env: str = "dev"
    database_url: AnyUrl | str = "sqlite:////data/notebookrefs.db"
    data_dir: Path = Path("/data")
    max_concurrent_scrapes: int = 4
    queue_broker: str = "inline"
    wayback_user_agent: str = "NotebookRefsBot/0.1"

    @field_validator("env")
    def _validate_env(cls, v: str) -> str:  # noqa: D401
        if v not in {"dev", "prod"}:
            raise ValueError("ENV must be either 'dev' or 'prod'")
        return v

    # Pydantic v2+ configuration pattern
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings() 