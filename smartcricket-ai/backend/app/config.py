from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    database_url: str = "postgresql+psycopg://localhost/smartcricket"
    jwt_secret: str = "dev-only-secret-change-me-in-the-env-file"
    token_hours: int = 24

    max_image_mb: int = 10
    max_video_mb: int = 50
    min_visibility: float = 0.5
    uncertain_threshold: float = 0.5

    # Comma-separated emails that get the administrator role (reference clips, model results)
    admin_emails: str = ""
    # Video mode: "cpu", "mps" (Apple GPU) or "cuda"
    torch_device: str = "cpu"
    video_pose_model: str = "full"

    llm_provider: str = "openai"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    # Gemini models tried in order when the main one is busy
    llm_fallback_models: str = "gemini-3.8-flash,gemini-flash-latest,gemini-3.1-flash-lite"

    upload_dir: Path = ROOT / "data" / "uploads"
    output_dir: Path = ROOT / "data" / "outputs"
    model_dir: Path = ROOT / "models"
    frontend_dir: Path = ROOT / "frontend"


settings = Settings()
ADMINS = {e.strip().lower() for e in settings.admin_emails.split(",") if e.strip()}
for d in (settings.upload_dir, settings.output_dir, settings.model_dir):
    d.mkdir(parents=True, exist_ok=True)
