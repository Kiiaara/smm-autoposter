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

    # SMTP для отправки кодов на почту (mail.ru)
    smtp_host: str = "smtp.mail.ru"
    smtp_port: int = 465  # SSL
    smtp_user: str = ""  # full email, например "kiiara@mail.ru"
    smtp_password: str = ""  # пароль приложения из настроек mail.ru
    smtp_from: str = ""  # с какого адреса слать (обычно = smtp_user)
    # whitelist email через запятую (для bootstrap первого юзера)
    auth_allowed_emails: str = ""

    # Telethon (MTProto): для сбора статистики из TG-каналов как юзер
    # api_id и api_hash с my.telegram.org, session_string - результат генератора telethon_login.py
    telethon_api_id: int = 0
    telethon_api_hash: str = ""
    telethon_session_string: str = ""
    # SOCKS5 прокси для Telethon (нужен на FirstVDS, где TG-DC заблокированы).
    # Если пусто - Telethon коннектится напрямую.
    telethon_proxy_host: str = ""
    telethon_proxy_port: int = 0
    # MTProxy для Telethon (альтернатива SOCKS5, надёжнее). Если задан - используется он.
    telethon_mtproxy_host: str = ""
    telethon_mtproxy_port: int = 0
    telethon_mtproxy_secret: str = ""

    # TGStat API (api.tgstat.ru) - для сбора статистики TG-каналов через REST.
    # Бесплатный тариф: 2 канала, ~500 запросов/день.
    tgstat_token: str = ""

    # Токен для локального tg-коллектора - им скрипт на компе авторизуется
    # при пуше собранной статистики на /api/stats/tg/push.
    tg_collector_token: str = ""

    # SOCKS5 прокси для исходящих запросов к api.telegram.org (нужен на РФ-сервере,
    # где TG-API блочится РКН). Формат: socks5://127.0.0.1:1080. Пусто = прямое подключение.
    tg_proxy_url: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
