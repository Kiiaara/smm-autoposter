import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import settings
from database import engine, Base
import models  # ensure all models are registered
from scheduler import start_scheduler, stop_scheduler
from routers import posts, channels, schedule_slots, upload, calendar, reminders, app_settings, stats


@asynccontextmanager
async def lifespan(app: FastAPI):
    # create tables
    Base.metadata.create_all(bind=engine)
    # миграция: сделать reminders.send_at nullable (для авто-напоминаний)
    _migrate_reminders_send_at_nullable()
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
