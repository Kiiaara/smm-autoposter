from datetime import datetime, timedelta
from html import escape
from sqlalchemy.orm import Session
from database import SessionLocal
from models.reminder import Reminder
from models.post import PostTarget, PostTargetStatus
from config import settings
from publishers.telegram import send_reminder

AFTER_PUBLISH_DELAY = timedelta(minutes=2)


def _published_at(db: Session, post_id: int):
    # самое раннее время публикации среди успешных таргетов
    times = db.query(PostTarget.published_at).filter(
        PostTarget.post_id == post_id,
        PostTarget.status == PostTargetStatus.published,
        PostTarget.published_at.isnot(None),
    ).all()
    times = [t[0] for t in times if t[0]]
    if not times:
        return None
    return min(times)


def _build_status_block(db: Session, post_id: int) -> str:
    # кликабельные ссылки на опубликованные таргеты + список ошибок (HTML)
    targets = db.query(PostTarget).filter(PostTarget.post_id == post_id).all()
    if not targets:
        return ""

    ok_lines = []
    fail_lines = []
    for t in targets:
        platform = t.channel.platform.value.upper() if t.channel else "?"
        name = t.channel.name if t.channel else f"channel#{t.channel_id}"
        name_html = escape(name)
        if t.status == PostTargetStatus.published and t.published_url:
            ok_lines.append(f'• [{platform}] <a href="{escape(t.published_url)}">{name_html}</a>')
        elif t.status == PostTargetStatus.failed:
            err = escape(t.error or "неизвестная ошибка")
            fail_lines.append(f"• [{platform}] <b>{name_html}</b>\n   <code>{err}</code>")

    parts = []
    if ok_lines:
        parts.append("\n<b>Опубликовано:</b>\n" + "\n".join(ok_lines))
    if fail_lines:
        parts.append("\n<b>⚠️ Ошибки:</b>\n" + "\n".join(fail_lines))
    return "\n".join(parts)


async def send_due_reminders():
    db: Session = SessionLocal()
    try:
        now = datetime.now()
        candidates = db.query(Reminder).filter(Reminder.sent == False).all()

        token = settings.reminder_bot_token
        chat_id = settings.reminder_chat_id
        if not token or not chat_id:
            return

        for reminder in candidates:
            # определяем эффективное время отправки
            if reminder.send_at is None:
                # авто-напоминание: published_at + 2 мин
                pub = _published_at(db, reminder.post_id)
                if not pub:
                    # проверяем не упало ли всё (тогда тоже стоит пинговать)
                    failed = db.query(PostTarget).filter(
                        PostTarget.post_id == reminder.post_id,
                        PostTarget.status == PostTargetStatus.failed,
                    ).count()
                    total = db.query(PostTarget).filter(
                        PostTarget.post_id == reminder.post_id,
                    ).count()
                    if total > 0 and failed == total:
                        # все упали - пингуем сразу
                        effective_at = now
                    else:
                        continue  # пост ещё не публиковался / в процессе
                else:
                    effective_at = pub + AFTER_PUBLISH_DELAY
            else:
                effective_at = reminder.send_at

            if effective_at > now:
                continue

            status_block = _build_status_block(db, reminder.post_id)
            message = escape(reminder.message) + ("\n" + status_block if status_block else "")
            ok = await send_reminder(token, chat_id, message, parse_mode="HTML")
            if ok:
                reminder.sent = True
                reminder.sent_at = now

        db.commit()
    finally:
        db.close()


async def send_publish_failure_alert(post_id: int, post_title: str | None = None):
    """Мгновенный пинг при ошибках публикации (независимо от reminder'ов)."""
    token = settings.reminder_bot_token
    chat_id = settings.reminder_chat_id
    if not token or not chat_id:
        return

    db: Session = SessionLocal()
    try:
        failed = db.query(PostTarget).filter(
            PostTarget.post_id == post_id,
            PostTarget.status == PostTargetStatus.failed,
        ).all()
        if not failed:
            return

        title = escape(post_title) if post_title else f"пост #{post_id}"
        lines = [f"⚠️ <b>Ошибка публикации</b>: {title}", ""]
        for t in failed:
            platform = t.channel.platform.value.upper() if t.channel else "?"
            name = escape(t.channel.name if t.channel else f"channel#{t.channel_id}")
            err = escape(t.error or "неизвестная ошибка")
            lines.append(f"• [{platform}] <b>{name}</b>\n   <code>{err}</code>")
        await send_reminder(token, chat_id, "\n".join(lines), parse_mode="HTML")
    finally:
        db.close()
