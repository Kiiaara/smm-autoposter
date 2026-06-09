import os
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from config import settings
from database import engine, Base, SessionLocal
import models  # ensure all models are registered
from scheduler import start_scheduler, stop_scheduler
from routers import posts, channels, schedule_slots, upload, calendar, reminders, app_settings, stats, auth as auth_router
from routers.auth import SESSION_COOKIE


@asynccontextmanager
async def lifespan(app: FastAPI):
    # create tables
    Base.metadata.create_all(bind=engine)
    # миграция: сделать reminders.send_at nullable (для авто-напоминаний)
    _migrate_reminders_send_at_nullable()
    # миграция: новые колонки в channel_snapshots
    _migrate_channel_snapshots_add_cols()
    # миграция: добавить posts.text_tg_html
    _migrate_posts_add_html_col()
    # миграция: добавить allowed_users.email
    _migrate_allowed_users_add_email()
    # перенос whitelist из .env в БД при первом запуске
    from routers.auth import _bootstrap_allowed_from_env
    _bootstrap_allowed_from_env()
    # ensure uploads dir exists
    os.makedirs(settings.upload_dir, exist_ok=True)
    # start background scheduler
    start_scheduler(settings.scheduler_interval_seconds)
    yield
    stop_scheduler()


app = FastAPI(title="Otlozhka ot Kiiara", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Auth middleware: блокируем все /api/* кроме whitelist
PUBLIC_PATHS = {
    "/api/health",
    "/api/auth/telegram", "/api/auth/me", "/api/auth/logout", "/api/auth/config",
    "/api/auth/bot/start", "/api/auth/bot/check",
    "/api/auth/email/request", "/api/auth/email/verify",
    # TG-коллектор - авторизуется своим токеном в заголовке
    "/api/stats/tg/sync/channels", "/api/stats/tg/sync/push",
}
PUBLIC_PREFIXES = ("/api/auth/bot/webhook/", "/api/stats/tg/embed/", "/api/stats/tg/asset")


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    # пропускаем не-api запросы (фронт сам разрулит на /login)
    if not path.startswith("/api/"):
        return await call_next(request)
    # пропускаем public пути
    if path in PUBLIC_PATHS:
        return await call_next(request)
    if any(path.startswith(p) for p in PUBLIC_PREFIXES):
        return await call_next(request)
    # если ни один способ авторизации не настроен (локалка) - пропускаем
    if not settings.auth_bot_token and not settings.smtp_user:
        return await call_next(request)

    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return JSONResponse({"detail": "Не авторизован"}, status_code=401)
    db = SessionLocal()
    try:
        sess = db.get(models.AuthSession, token)
        if not sess or sess.expires_at < datetime.now():
            return JSONResponse({"detail": "Сессия истекла"}, status_code=401)
        # проверка что юзер всё ещё в whitelist (мог быть удалён админом)
        allowed = db.get(models.AllowedUser, sess.tg_id)
        if not allowed:
            return JSONResponse({"detail": "Доступ отозван"}, status_code=403)
    finally:
        db.close()
    return await call_next(request)

# serve uploaded media
app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")

# API routers
app.include_router(posts.router)
app.include_router(channels.router)
app.include_router(schedule_slots.router)
app.include_router(upload.router)
app.include_router(calendar.router)
app.include_router(reminders.router)
app.include_router(app_settings.router)
app.include_router(stats.router)
app.include_router(auth_router.router)


def _migrate_posts_add_html_col():
    from sqlalchemy import text
    with engine.begin() as conn:
        existing = conn.execute(text("PRAGMA table_info(posts)")).fetchall()
        if "text_tg_html" not in {row[1] for row in existing}:
            conn.execute(text("ALTER TABLE posts ADD COLUMN text_tg_html TEXT"))


def _migrate_allowed_users_add_email():
    from sqlalchemy import text
    with engine.begin() as conn:
        existing = conn.execute(text("PRAGMA table_info(allowed_users)")).fetchall()
        if "email" not in {row[1] for row in existing}:
            conn.execute(text("ALTER TABLE allowed_users ADD COLUMN email TEXT"))
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_allowed_users_email ON allowed_users(email)"))


def _migrate_channel_snapshots_add_cols():
    """Добавляем avg_views/avg_likes/avg_reposts/avg_comments/posts_total если их нет."""
    from sqlalchemy import text
    new_cols = [
        ("avg_views", "INTEGER DEFAULT 0"),
        ("avg_likes", "INTEGER DEFAULT 0"),
        ("avg_reposts", "INTEGER DEFAULT 0"),
        ("avg_comments", "INTEGER DEFAULT 0"),
        ("posts_total", "INTEGER DEFAULT 0"),
    ]
    with engine.begin() as conn:
        existing = conn.execute(text("PRAGMA table_info(channel_snapshots)")).fetchall()
        existing_names = {row[1] for row in existing}
        for col, ddl in new_cols:
            if col not in existing_names:
                conn.execute(text(f"ALTER TABLE channel_snapshots ADD COLUMN {col} {ddl}"))


def _migrate_reminders_send_at_nullable():
    # SQLite: грязный трюк через writable_schema для смены NOT NULL → NULL
    from sqlalchemy import text
    with engine.begin() as conn:
        row = conn.execute(text("SELECT sql FROM sqlite_master WHERE type='table' AND name='reminders'")).fetchone()
        if not row or "send_at DATETIME NOT NULL" not in row[0]:
            return
        new_sql = row[0].replace("send_at DATETIME NOT NULL", "send_at DATETIME")
        conn.execute(text("PRAGMA writable_schema = ON"))
        conn.execute(text("UPDATE sqlite_master SET sql = :sql WHERE type='table' AND name='reminders'"), {"sql": new_sql})
        conn.execute(text("PRAGMA writable_schema = OFF"))


@app.get("/api/health")
def health():
    return {"ok": True}
