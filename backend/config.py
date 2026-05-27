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

    # TG-логин: бот через которого логинимся (домен должен быть привязан к нему в BotFather)
    # обычно тот же что reminder_bot_token
    auth_bot_token: str = ""
    # username бота без @ (для deeplink t.me/<username>?start=...)
    auth_bot_username: str = ""
    # секрет в URL webhook'а - чтобы случайные запросы не дёргали хэндлер
    # webhook URL будет /api/auth/bot/webhook/<secret>
    auth_webhook_secret: str = ""
    # белый список tg_id через запятую: "327410144,123456789"
    auth_allowed_tg_ids: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
