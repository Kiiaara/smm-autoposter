"""Одноразовый скрипт: получает session_string для Telethon.

Запуск:
    cd /opt/smm-autoposter/backend
    .venv/bin/python -m scripts.telethon_login

Спросит API_ID, API_HASH (если не в .env), номер телефона, код из TG.
Выведет TELETHON_SESSION_STRING - вставить в .env.
"""
import asyncio
import os
import sys

# подгружаем .env вручную если запускаем не через uvicorn
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from telethon import TelegramClient
from telethon.sessions import StringSession


async def main():
    api_id = os.environ.get("TELETHON_API_ID") or input("API_ID: ").strip()
    api_hash = os.environ.get("TELETHON_API_HASH") or input("API_HASH: ").strip()
    if not api_id or not api_hash:
        print("Нужны API_ID и API_HASH (с my.telegram.org)")
        sys.exit(1)

    print("\nВойди в TG-аккаунт (от него будет идти чтение статистики каналов).")
    print("Телефон с плюсом и кодом страны, например +79991234567\n")

    async with TelegramClient(StringSession(), int(api_id), api_hash) as client:
        me = await client.get_me()
        session = client.session.save()
        print()
        print("=" * 60)
        print(f"Вошёл как: {me.first_name} (@{me.username or '-'}) id={me.id}")
        print("=" * 60)
        print()
        print("TELETHON_SESSION_STRING=" + session)
        print()
        print("Скопируй строку выше (одну строку с равно), добавь в /opt/smm-autoposter/backend/.env")
        print("Затем: systemctl restart otlozhka-backend")


if __name__ == "__main__":
    asyncio.run(main())
