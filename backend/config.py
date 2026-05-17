from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./smm.db"
    upload_dir: str = "./uploads"
    # public URL where uploads are accessible (change to VPS domain in prod)
    base_url: str = "http://localhost:8000"
    max_upload_size_mb: int = 20
    scheduler_interval_seconds: int = 60
    # TG bot token and chat_id for personal reminders (set in .env or settings UI)
    reminder_bot_token: str = ""
    reminder_chat_id: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
