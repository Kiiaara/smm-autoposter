"""Одноразовый скрипт: получает session_string для Pyrogram.

Запуск:
    cd /opt/smm-autoposter/backend
    .venv/bin/python -m scripts.telethon_login

Спросит API_ID, API_HASH (если не в .env), номер телефона, код из TG.
Выведет TELETHON_SESSION_STRING - вставить в .env.
"""
import asyncio
import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from pyrogram import Client


async def main():
    api_id = os.environ.get("TELETHON_API_ID") or input("API_ID: ").strip()
    api_hash = os.environ.get("TELETHON_API_HASH") or input("API_HASH: ").strip()
    if not api_id or not api_hash:
        print("Нужны API_ID и API_HASH (с my.telegram.org)")
        sys.exit(1)

    kwargs = {
        "name": "login_tmp",
        "api_id": int(api_id),
        "api_hash": api_hash,
        "in_memory": True,
    }

    # MTProxy если задан
    mtp_host = os.environ.get("TELETHON_MTPROXY_HOST")
    mtp_port = os.environ.get("TELETHON_MTPROXY_PORT")
    mtp_secret = os.environ.get("TELETHON_MTPROXY_SECRET")
    if mtp_host and mtp_port and mtp_secret:
        kwargs["proxy"] = {
            "scheme": "mtproxy",
            "hostname": mtp_host,
            "port": int(mtp_port),
            "secret": mtp_secret,
        }
        print(f"\nИспользую MTProxy {mtp_host}:{mtp_port}\n")
    else:
        proxy_host = os.environ.get("TELETHON_PROXY_HOST")
        proxy_port = os.environ.get("TELETHON_PROXY_PORT")
        if proxy_host and proxy_port:
            kwargs["proxy"] = {
                "scheme": "socks5",
                "hostname": proxy_host,
                "port": int(proxy_port),
            }
            print(f"\nИспользую SOCKS5 {proxy_host}:{proxy_port}\n")

    print("Войди в TG-аккаунт (от него будет идти чтение статистики каналов).")
    print("Телефон с плюсом и кодом страны, например +79991234567\n")

    async with Client(**kwargs) as client:
        me = await client.get_me()
        session = await client.export_session_string()
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
