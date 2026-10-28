"""Centralised configuration — every setting comes from .env or defaults.

Why a single Settings class: keeps all env-var reading in one place, makes
it easy to verify no secrets are hardcoded, and lets tests override values.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Reads .env at project root; all fields have safe defaults so the app
    can start in demo mode with zero configuration."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Gemini ---------------------------------------------------------
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # --- Gmail OAuth ----------------------------------------------------
    google_credentials_path: str = "credentials.json"
    google_token_path: str = "token.json"

    # --- External services (all optional) --------------------------------
    safe_browsing_api_key: str = ""
    virustotal_api_key: str = ""

    # --- Models (Stage 4+) ----------------------------------------------
    nli_model: str = "cross-encoder/nli-MiniLM2-L6-H768"
    hf_phishing_model: str = ""

    # --- App -------------------------------------------------------------
    demo_mode: bool = True
    db_url: str = f"sqlite:///{PROJECT_ROOT / 'aegis.db'}"

    # --- Thresholds (§7, §8, §9) -----------------------------------------
    fraud_threshold: float = 0.5
    priority_high_threshold: float = 70.0
    priority_low_threshold: float = 30.0

    # --- Derived paths (resolved relative to project root, §14) ----------
    @property
    def credentials_path(self) -> Path:
        """Absolute path to the OAuth client-secrets file."""
        p = Path(self.google_credentials_path)
        return p if p.is_absolute() else PROJECT_ROOT / p

    @property
    def token_path(self) -> Path:
        """Absolute path to the cached OAuth token file."""
        p = Path(self.google_token_path)
        return p if p.is_absolute() else PROJECT_ROOT / p


settings = Settings()
