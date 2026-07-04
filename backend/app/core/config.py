"""Application configuration.

All secrets are read from a local ``.env`` file (never committed, never sent
anywhere). Copy ``.env.example`` to ``.env`` and fill in your own values.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root = two levels up from this file: backend/app/core/config.py -> project root
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_ROOT / "data"
ENV_FILE = PROJECT_ROOT / "backend" / ".env"


class Settings(BaseSettings):
    """Runtime settings loaded from environment / .env file."""

    # --- General ---
    app_name: str = "Risk Cockpit"
    environment: str = "development"
    # Single-user for now; every record still carries this id so multi-user is a
    # config change later, not a rewrite.
    default_user_id: str = "local-user"

    # --- Market data provider: "csv" (offline, default) or "angelone" (live) ---
    data_provider: str = "csv"

    # --- Angel One SmartAPI credentials (only needed when data_provider="angelone") ---
    angel_api_key: str = ""
    angel_client_code: str = ""
    angel_pin: str = ""
    angel_totp_secret: str = ""

    # --- Market-data feed (DATA ONLY: instrument list, lot sizes, live prices —
    # never holdings): "none" (off) or "angel". Uses the Angel creds above. ---
    market_data: str = "none"

    # --- AI explainer provider: "none" | "gemini" (free) | "claude" (paid) ---
    ai_provider: str = "none"

    # --- Google Gemini (free tier; only used when ai_provider="gemini") ---
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # --- Claude / Anthropic (paid; only used when ai_provider="claude") ---
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"

    # --- Database (SQLite file by default; swap to Postgres URL for multi-user) ---
    database_url: str = f"sqlite:///{(DATA_DIR / 'risk.db').as_posix()}"

    # --- CORS: where the frontend dev server runs ---
    frontend_origin: str = "http://localhost:5173"

    # --- Auth (multi-user) ---
    # Signs the session token — MUST be set to a long random value in production.
    secret_key: str = "dev-insecure-secret-change-in-production"
    jwt_expire_days: int = 30          # how long a login stays valid (per device)
    cookie_secure: bool = False        # True in production (HTTPS-only cookie)

    # --- Email (Resend) for verification + password reset ---
    resend_api_key: str = ""
    email_from: str = "RiskWise <onboarding@resend.dev>"
    # Where verify/reset links point (the frontend origin). The domain in production.
    app_base_url: str = "http://localhost:5173"

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def angel_configured(self) -> bool:
        return bool(
            self.angel_api_key
            and self.angel_client_code
            and self.angel_pin
            and self.angel_totp_secret
        )

    @property
    def market_enabled(self) -> bool:
        """Whether the Angel data-only market feed (prices/instruments) is on."""
        return self.market_data.lower() == "angel" and self.angel_configured

    @property
    def email_enabled(self) -> bool:
        """Whether real emails can be sent (Resend key present)."""
        return bool(self.resend_api_key)

    @property
    def gemini_configured(self) -> bool:
        return bool(self.gemini_api_key)

    @property
    def anthropic_configured(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def ai_configured(self) -> bool:
        """Whether the selected AI provider has what it needs to run."""
        if self.ai_provider == "gemini":
            return self.gemini_configured
        if self.ai_provider == "claude":
            return self.anthropic_configured
        return False


settings = Settings()

# Make sure the data directory exists for the SQLite file and sample CSVs.
DATA_DIR.mkdir(parents=True, exist_ok=True)
