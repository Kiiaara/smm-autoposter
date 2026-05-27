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
from models.login_request import LoginRequest
from models.email_code import EmailCode

router = APIRouter(prefix="/api/auth", tags=["auth"])

SESSION_COOKIE = "otlozhka_session"
SESSION_TTL_DAYS = 30
LOGIN_REQUEST_TTL_MINUTES = 10
EMAIL_CODE_TTL_MINUTES = 5
EMAIL_CODE_MAX_ATTEMPTS = 5


def _bootstrap_allowed_from_env():
    """При первом запуске переносим списки из .env (tg_ids и emails) в БД,
    чтобы юзер сразу мог зайти. Потом управление - через UI."""
    db = SessionLocal()
    try:
        # tg_ids
        raw = settings.auth_allowed_tg_ids or ""
        ids = [int(x.strip()) for x in raw.split(",") if x.strip().isdigit()]
        for tg_id in ids:
            existing = db.get(AllowedUser, tg_id)
            if not existing:
                db.add(AllowedUser(tg_id=tg_id, label="initial admin"))
        # emails - tg_id=0,-1,-2... как заглушка PK для email-only юзеров
        raw_emails = settings.auth_allowed_emails or ""
        emails = [e.strip().lower() for e in raw_emails.split(",") if e.strip()]
        for email in emails:
            existing = db.query(AllowedUser).filter(AllowedUser.email == email).first()
            if existing:
                continue
            # подбираем свободный отрицательный tg_id (заглушка для email-only)
            min_id = db.query(AllowedUser).filter(AllowedUser.tg_id < 0).order_by(AllowedUser.tg_id.asc()).first()
            next_id = (min_id.tg_id - 1) if min_id else -1
            db.add(AllowedUser(tg_id=next_id, label="initial admin", email=email))
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
    tg_id: Optional[int] = None
    email: Optional[str] = None
    label: Optional[str] = None


class AllowedUserRead(BaseModel):
    tg_id: int
    label: Optional[str] = None
    email: Optional[str] = None
    added_at: datetime
    is_self: bool = False

    model_config = {"from_attributes": True}


@router.get("/allowed", response_model=List[AllowedUserRead])
def list_allowed(user: AuthSession = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(AllowedUser).order_by(AllowedUser.added_at.asc()).all()
    return [
        AllowedUserRead(
            tg_id=r.tg_id, label=r.label, email=r.email,
            added_at=r.added_at, is_self=(r.tg_id == user.tg_id),
        )
        for r in rows
    ]


@router.post("/allowed", response_model=AllowedUserRead, status_code=201)
def add_allowed(data: AllowedUserCreate, user: AuthSession = Depends(get_current_user), db: Session = Depends(get_db)):
    has_tg = data.tg_id is not None and data.tg_id > 0
    email = _normalize_email(data.email) if data.email else None
    if email and ("@" not in email or "." not in email):
        raise HTTPException(400, "Некорректный email")
    if not has_tg and not email:
        raise HTTPException(400, "Укажите TG ID или email")

    if has_tg:
        existing = db.get(AllowedUser, data.tg_id)
        if existing:
            raise HTTPException(400, "Этот TG ID уже добавлен")
    if email:
        existing_email = db.query(AllowedUser).filter(AllowedUser.email == email).first()
        if existing_email:
            raise HTTPException(400, "Этот email уже добавлен")

    if has_tg:
        row = AllowedUser(tg_id=data.tg_id, label=data.label, email=email)
    else:
        # email-only: подбираем свободный отрицательный tg_id как заглушка PK
        min_id = db.query(AllowedUser).filter(AllowedUser.tg_id < 0).order_by(AllowedUser.tg_id.asc()).first()
        next_id = (min_id.tg_id - 1) if min_id else -1
        row = AllowedUser(tg_id=next_id, label=data.label, email=email)
    db.add(row)
    db.commit()
    db.refresh(row)
    return AllowedUserRead(
        tg_id=row.tg_id, label=row.label, email=row.email,
        added_at=row.added_at, is_self=False,
    )


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


# ── Login через бота (свой flow, без telegram-widget.js) ────
# Юзер жмёт "Войти" → фронт зовёт /bot/start → получает {token, deeplink}
# Юзер открывает deeplink t.me/<bot>?start=login_<token> → пишет боту /start
# TG шлёт webhook → бот ставит approved=true в LoginRequest
# Фронт поллит /bot/check?token=... → когда approved → ставим cookie сессии

class BotStartResponse(BaseModel):
    token: str
    deeplink: str
    expires_in: int  # секунд


def _cleanup_expired_requests(db: Session):
    db.query(LoginRequest).filter(LoginRequest.expires_at < datetime.now()).delete()
    db.commit()


def _set_session_cookie(response: Response, db: Session, tg_id: int, username: Optional[str], first_name: Optional[str]) -> str:
    token = secrets.token_hex(32)
    expires = datetime.now() + timedelta(days=SESSION_TTL_DAYS)
    db.add(AuthSession(
        token=token, tg_id=tg_id, tg_username=username,
        tg_first_name=first_name, expires_at=expires,
    ))
    db.commit()
    response.set_cookie(
        SESSION_COOKIE, token,
        max_age=SESSION_TTL_DAYS * 86400,
        httponly=True, secure=True, samesite="lax", path="/",
    )
    return token


@router.post("/bot/start", response_model=BotStartResponse)
def bot_login_start(db: Session = Depends(get_db)):
    """Создаёт запрос на вход. Возвращает deeplink, который фронт открывает в TG."""
    if not settings.auth_bot_username:
        raise HTTPException(500, "auth_bot_username не настроен на сервере")
    _cleanup_expired_requests(db)
    token = secrets.token_hex(16)  # 32 hex chars - помещается в /start (max 64)
    expires = datetime.now() + timedelta(minutes=LOGIN_REQUEST_TTL_MINUTES)
    db.add(LoginRequest(token=token, expires_at=expires))
    db.commit()
    deeplink = f"https://t.me/{settings.auth_bot_username}?start=login_{token}"
    return BotStartResponse(token=token, deeplink=deeplink, expires_in=LOGIN_REQUEST_TTL_MINUTES * 60)


@router.get("/bot/check")
def bot_login_check(token: str, response: Response, db: Session = Depends(get_db)):
    """Фронт поллит. Когда approved=true - ставим сессию и возвращаем user."""
    req = db.get(LoginRequest, token)
    if not req:
        raise HTTPException(404, "Запрос не найден")
    if req.expires_at < datetime.now():
        db.delete(req)
        db.commit()
        raise HTTPException(410, "Срок действия запроса истёк")
    if not req.approved:
        return {"approved": False}

    # подтверждено - проверяем whitelist
    tg_id = req.tg_id
    if not _has_any_users(db):
        db.add(AllowedUser(tg_id=tg_id, label=req.tg_first_name or req.tg_username or "owner"))
        db.commit()
    elif not _is_allowed(db, tg_id):
        db.delete(req)
        db.commit()
        raise HTTPException(403, f"Доступ запрещён. Твой TG ID: {tg_id}. Попроси администратора добавить тебя.")

    _set_session_cookie(response, db, tg_id, req.tg_username, req.tg_first_name)
    username = req.tg_username
    first_name = req.tg_first_name
    db.delete(req)
    db.commit()
    return {"approved": True, "tg_id": tg_id, "username": username, "first_name": first_name}


@router.post("/bot/webhook/{secret}")
async def bot_webhook(secret: str, request: Request, db: Session = Depends(get_db)):
    """Telegram шлёт сюда все апдейты бота. Ловим /start login_<token>."""
    if not settings.auth_webhook_secret or secret != settings.auth_webhook_secret:
        raise HTTPException(403, "forbidden")

    update = await request.json()
    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return {"ok": True}
    text = (msg.get("text") or "").strip()
    if not text.startswith("/start"):
        return {"ok": True}

    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        return {"ok": True}
    payload = parts[1].strip()
    if not payload.startswith("login_"):
        return {"ok": True}

    token = payload[len("login_"):]
    req = db.get(LoginRequest, token)
    if not req or req.expires_at < datetime.now():
        # отвечаем юзеру что ссылка протухла
        await _send_bot_message(msg["from"]["id"], "Ссылка устарела. Открой сайт и нажми \"Войти\" ещё раз.")
        return {"ok": True}

    user = msg.get("from") or {}
    req.tg_id = user.get("id")
    req.tg_username = user.get("username")
    req.tg_first_name = user.get("first_name")
    req.approved = True
    db.commit()

    await _send_bot_message(user.get("id"), f"Готово, {user.get('first_name') or 'друг'}! Возвращайся на сайт - ты залогинен.")
    return {"ok": True}


async def _send_bot_message(chat_id: int, text: str):
    if not settings.auth_bot_token or not chat_id:
        return
    import httpx
    url = f"https://api.telegram.org/bot{settings.auth_bot_token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            await c.post(url, json={"chat_id": chat_id, "text": text})
    except Exception:
        pass  # webhook не должен падать из-за проблем с отправкой


# ── Login через email + код ───────────────────────────────
# Юзер вводит email → шлём 6-значный код → юзер вводит код → ставим сессию

class EmailRequestIn(BaseModel):
    email: str


class EmailVerifyIn(BaseModel):
    email: str
    code: str


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _find_allowed_by_email(db: Session, email: str) -> Optional[AllowedUser]:
    return db.query(AllowedUser).filter(AllowedUser.email == email).first()


@router.post("/email/request")
def email_request(data: EmailRequestIn, db: Session = Depends(get_db)):
    """Шлёт 6-значный код на email. Только если email в whitelist (или БД пустая - bootstrap)."""
    email = _normalize_email(data.email)
    if "@" not in email or "." not in email:
        raise HTTPException(400, "Некорректный email")

    has_users = db.query(AllowedUser).first() is not None
    # bootstrap: первый юзер автоматом получает доступ
    if not has_users:
        # дадим войти, добавим в whitelist при verify
        pass
    else:
        if not _find_allowed_by_email(db, email):
            # не палим что email не в whitelist (антиспам) - но всё равно не шлём код
            # возвращаем такой же ответ как и для разрешённого, чтобы не было перебора
            return {"ok": True, "expires_in": EMAIL_CODE_TTL_MINUTES * 60}

    # инвалидируем старые активные коды для этого email
    db.query(EmailCode).filter(
        EmailCode.email == email,
        EmailCode.used == False,
        EmailCode.expires_at > datetime.now(),
    ).update({"used": True})

    code = f"{secrets.randbelow(1_000_000):06d}"
    db.add(EmailCode(
        email=email,
        code_hash=_hash_code(code),
        expires_at=datetime.now() + timedelta(minutes=EMAIL_CODE_TTL_MINUTES),
    ))
    db.commit()

    try:
        from services.email_sender import send_login_code
        send_login_code(email, code)
    except Exception as e:
        # код в БД остался, но письмо не ушло - сообщим юзеру
        raise HTTPException(500, f"Не удалось отправить письмо: {e}")

    return {"ok": True, "expires_in": EMAIL_CODE_TTL_MINUTES * 60}


@router.post("/email/verify")
def email_verify(data: EmailVerifyIn, response: Response, db: Session = Depends(get_db)):
    email = _normalize_email(data.email)
    code = data.code.strip()
    if not code.isdigit() or len(code) != 6:
        raise HTTPException(400, "Код должен состоять из 6 цифр")

    # ищем самый свежий неиспользованный код для этого email
    row = (
        db.query(EmailCode)
        .filter(EmailCode.email == email, EmailCode.used == False)
        .order_by(EmailCode.id.desc())
        .first()
    )
    if not row:
        raise HTTPException(400, "Код не найден или уже использован. Запросите новый.")
    if row.expires_at < datetime.now():
        raise HTTPException(410, "Срок действия кода истёк. Запросите новый.")
    if row.attempts >= EMAIL_CODE_MAX_ATTEMPTS:
        row.used = True
        db.commit()
        raise HTTPException(429, "Слишком много неверных попыток. Запросите новый код.")

    if row.code_hash != _hash_code(code):
        row.attempts += 1
        db.commit()
        remaining = EMAIL_CODE_MAX_ATTEMPTS - row.attempts
        raise HTTPException(400, f"Неверный код. Осталось попыток: {remaining}")

    # код верный
    row.used = True
    db.commit()

    # whitelist: если БД пустая - первый юзер становится админом
    has_users = db.query(AllowedUser).first() is not None
    if not has_users:
        db.add(AllowedUser(tg_id=-1, label=email, email=email))
        db.commit()

    user = _find_allowed_by_email(db, email)
    if not user:
        raise HTTPException(403, "Email не в списке разрешённых")

    _set_session_cookie(response, db, user.tg_id, None, user.label)
    return {"ok": True, "email": email, "label": user.label}
