import hashlib
import hmac
import secrets
from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Request, Response, Cookie
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import settings
from database import get_db, SessionLocal
from models.auth_session import AuthSession
from models.allowed_user import AllowedUser

router = APIRouter(prefix="/api/auth", tags=["auth"])

SESSION_COOKIE = "otlozhka_session"
SESSION_TTL_DAYS = 30


def _bootstrap_allowed_from_env():
    """При первом запуске переносим список из .env в БД (auth_allowed_tg_ids),
    чтобы юзер сразу мог зайти. Потом управление - через UI."""
    raw = settings.auth_allowed_tg_ids or ""
    ids = [int(x.strip()) for x in raw.split(",") if x.strip().isdigit()]
    if not ids:
        return
    db = SessionLocal()
    try:
        for tg_id in ids:
            existing = db.get(AllowedUser, tg_id)
            if not existing:
                db.add(AllowedUser(tg_id=tg_id, label="initial admin"))
        db.commit()
    finally:
        db.close()


def _is_allowed(db: Session, tg_id: int) -> bool:
    return db.get(AllowedUser, tg_id) is not None


def _has_any_users(db: Session) -> bool:
    return db.query(AllowedUser).first() is not None


def _verify_tg_signature(data: dict, bot_token: str) -> bool:
    received_hash = data.get("hash")
    if not received_hash:
        return False
    pairs = []
    for k, v in sorted(data.items()):
        if k == "hash":
            continue
        if v is None:
            continue
        pairs.append(f"{k}={v}")
    data_check_string = "\n".join(pairs)
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    expected = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, received_hash)


def get_current_user(otlozhka_session: Optional[str] = Cookie(None), db: Session = Depends(get_db)) -> AuthSession:
    if not otlozhka_session:
        raise HTTPException(401, "Не авторизован")
    sess = db.get(AuthSession, otlozhka_session)
    if not sess or sess.expires_at < datetime.now():
        raise HTTPException(401, "Сессия истекла")
    return sess


@router.post("/telegram")
async def telegram_login(request: Request, response: Response, db: Session = Depends(get_db)):
    if not settings.auth_bot_token:
        raise HTTPException(500, "auth_bot_token не настроен на сервере")

    data = await request.json()
    norm = {k: str(v) for k, v in data.items() if v is not None}

    if not _verify_tg_signature(norm, settings.auth_bot_token):
        raise HTTPException(401, "Невалидная подпись Telegram")

    try:
        auth_date = int(norm.get("auth_date", "0"))
    except ValueError:
        raise HTTPException(400, "Некорректный auth_date")
    if datetime.now().timestamp() - auth_date > 86400:
        raise HTTPException(401, "Срок действия авторизации истёк, попробуй снова")

    tg_id = int(norm.get("id", "0"))

    # если в БД вообще нет пользователей - первый вошедший становится админом
    if not _has_any_users(db):
        db.add(AllowedUser(tg_id=tg_id, label=norm.get("first_name") or norm.get("username") or "owner"))
        db.commit()
    elif not _is_allowed(db, tg_id):
        raise HTTPException(403, f"Доступ запрещён. Твой TG ID: {tg_id}. Попроси администратора добавить тебя.")

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
def me(user: AuthSession = Depends(get_current_user)):
    return {
        "tg_id": user.tg_id,
        "username": user.tg_username,
        "first_name": user.tg_first_name,
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


# ── Управление списком разрешённых пользователей ──────────

class AllowedUserCreate(BaseModel):
    tg_id: int
    label: Optional[str] = None


class AllowedUserRead(BaseModel):
    tg_id: int
    label: Optional[str] = None
    added_at: datetime
    is_self: bool = False

    model_config = {"from_attributes": True}


@router.get("/allowed", response_model=List[AllowedUserRead])
def list_allowed(user: AuthSession = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(AllowedUser).order_by(AllowedUser.added_at.asc()).all()
    return [
        AllowedUserRead(tg_id=r.tg_id, label=r.label, added_at=r.added_at, is_self=(r.tg_id == user.tg_id))
        for r in rows
    ]


@router.post("/allowed", response_model=AllowedUserRead, status_code=201)
def add_allowed(data: AllowedUserCreate, user: AuthSession = Depends(get_current_user), db: Session = Depends(get_db)):
    existing = db.get(AllowedUser, data.tg_id)
    if existing:
        raise HTTPException(400, "Этот TG ID уже добавлен")
    row = AllowedUser(tg_id=data.tg_id, label=data.label)
    db.add(row)
    db.commit()
    db.refresh(row)
    return AllowedUserRead(tg_id=row.tg_id, label=row.label, added_at=row.added_at, is_self=False)


@router.delete("/allowed/{tg_id}")
def remove_allowed(tg_id: int, user: AuthSession = Depends(get_current_user), db: Session = Depends(get_db)):
    if tg_id == user.tg_id:
        raise HTTPException(400, "Нельзя удалить самого себя")
    row = db.get(AllowedUser, tg_id)
    if not row:
        raise HTTPException(404, "Пользователь не найден")
    db.delete(row)
    # инвалидируем все активные сессии этого юзера
    db.query(AuthSession).filter(AuthSession.tg_id == tg_id).delete()
    db.commit()
    return {"ok": True}
