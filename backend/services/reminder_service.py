import re
from datetime import datetime, timedelta
from html import escape
import httpx
from sqlalchemy.orm import Session
from database import SessionLocal
from models.reminder import Reminder
from models.post import PostTarget, PostTargetStatus
from config import settings
from publishers.telegram import send_reminder


async def send_vk_alert(text_html: str) -> bool:
    """Отправка алерта в VK-личку. Работает без прокси (VK доступен с РФ).
    text_html - HTML-текст, тут конвертим в plain для VK. Возвращает True если отправлено."""
    token = settings.alert_vk_token
    user_id = settings.alert_vk_user_id
    if not token or not user_id:
        return False
    # HTML → plain: убираем теги, декодим &amp; и т.д.
    from html import unescape
    plain = re.sub(r'<br\s*/?>', '\n', text_html, flags=re.IGNORECASE)
    plain = re.sub(r'</p>|</div>', '\n', plain, flags=re.IGNORECASE)
    plain = re.sub(r'<[^>]+>', '', plain)
    plain = unescape(plain).strip()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post("https://api.vk.com/method/messages.send", params={
                "user_id": user_id,
                "message": plain,
                "random_id": int(datetime.now().timestamp() * 1000),
                "access_token": token,
                "v": "5.131",
            })
        data = r.json()
        if data.get("error"):
            print(f"[alert] VK send error: {data['error']}", flush=True)
            return False
        return True
    except Exception as e:
        print(f"[alert] VK send exception: {e}", flush=True)
        return False


async def send_alert(text_html: str):
    """Универсальная отправка алерта. Приоритет: VK-личка (работает без прокси),
    fallback - TG (может висеть если прокси мёртв, но пробуем)."""
    if await send_vk_alert(text_html):
        return
    # fallback на TG
    token = settings.reminder_bot_token
    chat_id = settings.reminder_chat_id
    if not token or not chat_id:
        return
    try:
        await send_reminder(token, chat_id, text_html, parse_mode="HTML")
    except Exception as e:
        print(f"[alert] TG fallback failed too: {e}", flush=True)

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


async def send_noon_post_links(post_id: int, post_title: str | None = None):
    """Авто-сообщение для постов опубликованных в 12:00 - сразу шлёт ссылки."""
    token = settings.reminder_bot_token
    chat_id = settings.reminder_chat_id
    if not token or not chat_id:
        return

    db: Session = SessionLocal()
    try:
        status_block = _build_status_block(db, post_id)
        if not status_block:
            return
        title = escape(post_title) if post_title else "Полуденный пост"
        message = f"🕛 <b>{title}</b> опубликован" + "\n" + status_block
        await send_reminder(token, chat_id, message, parse_mode="HTML")
    finally:
        db.close()


async def send_publish_failure_alert(post_id: int, post_title: str | None = None):
    """Мгновенный пинг при ошибках публикации (независимо от reminder'ов).
    Идёт через send_alert - VK-личка приоритет, TG fallback."""
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
        await send_alert("\n".join(lines))
    finally:
        db.close()
