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

    # --- Models (Stage 3 & Stage 4+) -----------------------------------
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    nli_model: str = "cross-encoder/nli-MiniLM2-L6-H768"
    hf_phishing_model: str = ""

    # --- App -------------------------------------------------------------
    demo_mode: bool = True
    db_url: str = f"sqlite:///{PROJECT_ROOT / 'aegis.db'}"

    # --- Sync Window -----------------------------------------------------
    sync_days: int = 14
    sync_max: int = 100
    sent_days: int = 90
    rag_history_max: int = 200

    # --- Priority & RAG Parameters (§Stage 3) ---------------------------
    priority_rule_weight: float = 0.4
    priority_gemini_weight: float = 0.6
    priority_skip_gemini_promo: bool = True
    max_body_chars_for_llm: int = 2000
    max_body_chars_for_rag: int = 500

    # --- Thresholds & Phishing (§7, §16, Stage 4) -----------------------
    fraud_version: str = "v1"
    fraud_threshold: float = 0.5
    fraud_suspicious_threshold: float = 0.3
    strong_layer_threshold: float = 0.8
    strong_layer_floor: float = 0.6
    weak_signal_cap: float = 0.40
    trust_score_reduction: float = 0.3
    gemini_social_trigger_threshold: float = 0.25

    # Phishing provider weights (§16)
    weight_sender_auth: float = 0.35
    weight_url_heuristics: float = 0.35
    weight_bert_phishing: float = 0.15
    weight_gemini_social: float = 0.15

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
