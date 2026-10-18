"""Runtime settings, read from environment variables (or a local .env file)."""

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "dev"
    google_cloud_project: str = "royastacxk-aibuildercup"
    google_cloud_location: str = "asia-south1"
    google_genai_use_vertexai: bool = True
    gemini_location: str = "global"  # Vertex endpoint for Gemini; Firestore/BigQuery stay in google_cloud_location
    gemini_api_key: str = ""  # Gemini API (AI Studio) key: the whole client when Vertex is off; with Vertex on, only the last-resort embedding endpoint

    # Verified on Vertex AI (global) 15 Oct 2026: 3.5-flash ~1.4 s, 3.1-pro-preview ~3 s. The 2.5 models
    # are no longer served. On a free-tier AI Studio key use gemini-3-flash-preview / gemini-3.1-flash-lite.
    gemini_flash_model: str = "gemini-3.5-flash"
    gemini_pro_model: str = "gemini-3.1-pro-preview"
    gemini_live_model: str = "gemini-live-2.5-flash"   # speech-to-speech; Vertex default, or an AI Studio model when the live key is set
    gemini_live_api_key: str = ""                      # AI Studio key for the live bridge only (newer live models land there first)
    gemini_live_affective: bool = True                 # affective dialog; some models (gemini-3.8-live) reject the option

    cors_origins: list[str] = ["http://localhost:3000"]

    qr_session_signing_key: str = "dev-only-change-me"
    app_base_url: str = "http://localhost:3000"  # printed in QR codes
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    job_key: str = ""   # shared secret for /jobs/* (Cloud Scheduler sends it as X-Job-Key)

    @model_validator(mode="after")
    def _no_default_key_outside_dev(self):
        if self.env not in ("dev", "test") and self.qr_session_signing_key == "dev-only-change-me":
            raise ValueError("QR_SESSION_SIGNING_KEY must be set when ENV is not dev/test")
        return self


settings = Settings()
