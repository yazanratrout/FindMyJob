"""Application configuration.

Secrets and environment-specific values are read from the process environment
(and, for local development, from a ``.env`` file at the repo root). Everything
that a *user* tunes at runtime — cities, keywords, weights, schedule — lives in
the database (see :mod:`findmyjob.models.config`), not here.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Process-level configuration, populated from the environment / ``.env``."""

    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    # ---- Application ------------------------------------------------------
    app_env: str = Field(default="development", alias="APP_ENV")
    secret_key: str = Field(default="dev-insecure-change-me", alias="APP_SECRET_KEY")
    data_dir: Path = Field(default=REPO_ROOT / "data", alias="APP_DATA_DIR")
    database_url_override: str | None = Field(default=None, alias="APP_DATABASE_URL")
    host: str = Field(default="127.0.0.1", alias="APP_HOST")
    port: int = Field(default=8000, alias="APP_PORT")

    # ---- LLM -------------------------------------------------------------
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    llm_model_cheap: str = Field(default="claude-haiku-4-5-20251001", alias="LLM_MODEL_CHEAP")
    llm_model_smart: str = Field(default="claude-sonnet-5", alias="LLM_MODEL_SMART")
    llm_monthly_budget_eur: float = Field(default=10.0, alias="LLM_MONTHLY_BUDGET_EUR")
    # Approximate prices in EUR per 1M tokens. Update to match current pricing.
    llm_price_cheap_in: float = Field(default=0.80, alias="LLM_PRICE_CHEAP_IN")
    llm_price_cheap_out: float = Field(default=4.00, alias="LLM_PRICE_CHEAP_OUT")
    llm_price_smart_in: float = Field(default=2.80, alias="LLM_PRICE_SMART_IN")
    llm_price_smart_out: float = Field(default=14.00, alias="LLM_PRICE_SMART_OUT")

    # ---- Job source credentials ---------------------------------------
    ba_api_client_id: str | None = Field(default=None, alias="BA_API_CLIENT_ID")
    ba_api_client_secret: str | None = Field(default=None, alias="BA_API_CLIENT_SECRET")
    adzuna_app_id: str | None = Field(default=None, alias="ADZUNA_APP_ID")
    adzuna_app_key: str | None = Field(default=None, alias="ADZUNA_APP_KEY")
    themuse_api_key: str | None = Field(default=None, alias="THEMUSE_API_KEY")

    # ---- Notifications -------------------------------------------------
    smtp_host: str | None = Field(default=None, alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_user: str | None = Field(default=None, alias="SMTP_USER")
    smtp_password: str | None = Field(default=None, alias="SMTP_PASSWORD")
    smtp_from: str | None = Field(default=None, alias="SMTP_FROM")
    telegram_bot_token: str | None = Field(default=None, alias="TELEGRAM_BOT_TOKEN")

    # ---- Derived --------------------------------------------------------
    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        if self.database_url_override:
            return self.database_url_override
        return f"sqlite:///{(self.data_dir / 'findmyjob.db').as_posix()}"

    @property
    def documents_dir(self) -> Path:
        return self.data_dir / "documents"

    @property
    def letters_dir(self) -> Path:
        return self.data_dir / "letters"

    @property
    def models_dir(self) -> Path:
        return self.data_dir / "models"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def backups_dir(self) -> Path:
        return self.data_dir / "backups"

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"production", "prod"}

    def ensure_dirs(self) -> None:
        """Create every runtime directory the app writes to."""
        for path in (
            self.data_dir,
            self.documents_dir,
            self.letters_dir,
            self.models_dir,
            self.logs_dir,
            self.backups_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached :class:`Settings` singleton."""
    settings = Settings()
    settings.ensure_dirs()
    return settings


def reset_settings_cache() -> None:
    """Clear the cached settings (used by tests)."""
    get_settings.cache_clear()
