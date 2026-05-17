import os
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from config import settings

router = APIRouter(prefix="/api/settings", tags=["settings"])


class ReminderBotConfig(BaseModel):
    bot_token: str = ""
    chat_id: str


def _persist_env(updates: dict):
    """Persist key=value pairs to .env file, preserving existing keys."""
    env_path = ".env"
    lines = []
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            lines = f.readlines()

    updated_keys = set()
    new_lines = []
    for line in lines:
        key = line.split("=")[0].strip()
        if key in updates:
            new_lines.append(f"{key}={updates[key]}\n")
            updated_keys.add(key)
        else:
            new_lines.append(line)
    for key, val in updates.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={val}\n")

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)


@router.put("/reminder-bot")
def set_reminder_bot(data: ReminderBotConfig):
    """Save reminder bot config. Empty bot_token = keep existing."""
    updates = {"REMINDER_CHAT_ID": data.chat_id}
    settings.reminder_chat_id = data.chat_id

    if data.bot_token:
        settings.reminder_bot_token = data.bot_token
        updates["REMINDER_BOT_TOKEN"] = data.bot_token

    _persist_env(updates)
    return {"ok": True}


@router.get("/reminder-bot")
async def get_reminder_bot():
    """Return bot config status. Token itself is never returned for security."""
    token = settings.reminder_bot_token
    chat_id = settings.reminder_chat_id
    bot_username = None

    if token:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(f"https://api.telegram.org/bot{token}/getMe")
            data = r.json()
            if data.get("ok"):
                bot_username = data["result"].get("username")
        except Exception:
            pass

    return {
        "bot_token_set": bool(token),
        "chat_id": chat_id,
        "bot_username": bot_username,
    }


@router.post("/reminder-bot/test")
async def test_reminder_bot():
    """Send a test message to the configured chat."""
    token = settings.reminder_bot_token
    chat_id = settings.reminder_chat_id

    if not token or not chat_id:
        raise HTTPException(400, "Бот не настроен - сначала сохрани токен и chat_id")

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": "✅ Тестовое сообщение от Otlozhka ot Kiiara - бот напоминаний работает!"}
        )
    data = r.json()
    if data.get("ok"):
        return {"ok": True}
    return {"ok": False, "message": data.get("description", "Ошибка отправки")}
