import hashlib
import hmac
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, Cookie
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models.auth_session import AuthSession

router = APIRouter(prefix="/api/auth", tags=["auth"])

SESSION_COOKIE = "otlozhka_session"
SESSION_TTL_DAYS = 30


def _allowed_ids() -> set[int]:
    raw = settings.auth_allowed_tg_ids or ""
    out = set()
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            out.add(int(part))
    return out


def _verify_tg_signature(data: dict, bot_token: str) -> bool:
    """Проверка подписи виджета Telegram Login.
    https://core.telegram.org/widgets/login#checking-authorization
    """
    received_hash = data.get("hash")
    if not received_hash:
        return False
    # формируем data_check_string из всех полей кроме hash, отсортированных по ключу
    pairs = []
    for k, v in sorted(data.items()):
        if k == "hash":
            continue
        if v is None:
            continue
        pairs.append(f"{k}={v}")
    data_check_string = "\n".join(pairs)
    # секрет = sha256 от bot_token
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    expected = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, received_hash)


@router.post("/telegram")
async def telegram_login(request: Request, response: Response, db: Session = Depends(get_db)):
    if not settings.auth_bot_token:
        raise HTTPException(500, "auth_bot_token не настроен на сервере")

    data = await request.json()
    # приводим к строкам как требует TG
    norm = {k: str(v) for k, v in data.items() if v is not None}

    if not _verify_tg_signature(norm, settings.auth_bot_token):
        raise HTTPException(401, "Невалидная подпись Telegram")

    # проверка возраста auth_date (не старше 24 часов)
    try:
        auth_date = int(norm.get("auth_date", "0"))
    except ValueError:
        raise HTTPException(400, "Некорректный auth_date")
    if datetime.now().timestamp() - auth_date > 86400:
        raise HTTPException(401, "Срок действия авторизации истёк, попробуй снова")

    tg_id = int(norm.get("id", "0"))
    allowed = _allowed_ids()
    if allowed and tg_id not in allowed:
        raise HTTPException(403, f"Доступ запрещён. Твой TG ID: {tg_id}. Добавь его в белый список на сервере.")

    # создаём сессию
    token = secrets.token_hex(32)
    expires = datetime.now() + timedelta(days=SESSION_TTL_DAYS)
    sess = AuthSession(
        token=token,
        tg_id=tg_id,
        tg_username=norm.get("username"),
        tg_first_name=norm.get("first_name"),
        expires_at=expires,
    )
    db.add(sess)
    db.commit()

    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_TTL_DAYS * 86400,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )
    return {"ok": True, "tg_id": tg_id, "username": norm.get("username"), "first_name": norm.get("first_name")}


@router.get("/me")
def me(otlozhka_session: Optional[str] = Cookie(None), db: Session = Depends(get_db)):
    if not otlozhka_session:
        raise HTTPException(401, "Не авторизован")
    sess = db.get(AuthSession, otlozhka_session)
    if not sess or sess.expires_at < datetime.now():
        raise HTTPException(401, "Сессия истекла")
    return {
        "tg_id": sess.tg_id,
        "username": sess.tg_username,
        "first_name": sess.tg_first_name,
    }


@router.post("/logout")
def logout(response: Response, otlozhka_session: Optional[str] = Cookie(None), db: Session = Depends(get_db)):
    if otlozhka_session:
        sess = db.get(AuthSession, otlozhka_session)
        if sess:
            db.delete(sess)
            db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@router.get("/config")
def auth_config():
    """Публичная инфа для фронта - имя бота для виджета."""
    # парсим bot_username из токена нельзя, надо хранить отдельно
    # либо вытащить через getMe - сделаем при необходимости
    return {"enabled": bool(settings.auth_bot_token and settings.auth_allowed_tg_ids)}
