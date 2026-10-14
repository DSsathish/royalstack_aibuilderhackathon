"""Runtime settings, read from environment variables (or a local .env file)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "dev"
    google_cloud_project: str = "royastacxk-aibuildercup"
    google_cloud_location: str = "asia-south1"
    google_genai_use_vertexai: bool = True
    gemini_api_key: str = ""  # only used when google_genai_use_vertexai is False

    gemini_flash_model: str = "gemini-3.5-flash"
    gemini_pro_model: str = "gemini-2.5-pro"

    cors_origins: list[str] = ["http://localhost:3000"]

    qr_session_signing_key: str = "dev-only-change-me"
    app_base_url: str = "http://localhost:3000"  # printed in QR codes
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""


settings = Settings()
