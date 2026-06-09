"""Сбор статистики TG-каналов прямо на сервере через Telethon (MTProto).

В отличие от tg_stats.py (TGStat REST API с квотой) - тут мы ходим в TG-датацентры
напрямую от имени юзера. Из РФ нужен SOCKS5-прокси (через xray на 127.0.0.1:1080).

Что нужно в .env:
  TELETHON_API_ID, TELETHON_API_HASH, TELETHON_SESSION_STRING  - креды от my.telegram.org
  TG_PROXY_URL=socks5://127.0.0.1:1080                          - SOCKS-туннель xray

Запуск: collect_all_tg_channels(db, period_days=30) - один раз, либо по кнопке.
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from config import settings
from models.channel import Channel, Platform
from models.stats import ChannelPost, ChannelSnapshot

log = logging.getLogger("tg_telethon_collector")


def is_configured() -> bool:
    return bool(
        settings.telethon_api_id
        and settings.telethon_api_hash
        and settings.telethon_session_string
    )


def _channel_username(ch: Channel) -> Optional[str]:
    cfg = ch.config_json or {}
    raw = (cfg.get("channel") or cfg.get("username") or "").strip()
    if not raw:
        return None
    if "t.me/" in raw:
        raw = raw.split("t.me/", 1)[1]
    if "telegram.me/" in raw:
        raw = raw.split("telegram.me/", 1)[1]
    username = raw.lstrip("@").strip("/").split("/")[0]
    if username.startswith("+") or username.startswith("joinchat"):
        return None
    return username or None


def _proxy_tuple() -> Optional[tuple]:
    """Преобразует TG_PROXY_URL (socks5://host:port) в кортеж для Telethon.
    Telethon ожидает (proto, host, port) либо (proto, host, port, true_or_false_rdns, user, pass).
    """
    url = settings.tg_proxy_url
    if not url:
        return None
    p = urlparse(url)
    scheme = (p.scheme or "").lower()
    host = p.hostname
    port = p.port
    if not host or not port:
        return None
    # python_socks принимает строки 'socks5', 'socks4', 'http'
    if scheme not in ("socks5", "socks4", "http"):
        return None
    return (scheme, host, port, True)


async def _collect_one(client, ch: Channel, period_days: int) -> Dict[str, Any]:
    """Собирает посты одного канала + текущее число подписчиков."""
    from telethon.tl.functions.channels import GetFullChannelRequest

    username = _channel_username(ch)
    if not username:
        return {"channel_id": ch.id, "ok": False, "error": "no username", "posts": []}

    try:
        entity = await client.get_entity(username)
    except Exception as e:
        return {"channel_id": ch.id, "ok": False, "error": f"get_entity: {e}", "posts": []}

    try:
        full = await client(GetFullChannelRequest(entity))
        subscribers = int(full.full_chat.participants_count or 0)
    except Exception as e:
        log.warning(f"GetFullChannel failed for {username}: {e}")
        subscribers = 0

    since = datetime.now() - timedelta(days=period_days)
    posts: List[Dict[str, Any]] = []

    async for msg in client.iter_messages(entity, limit=500):
        if not msg.date:
            continue
        # msg.date - tz-aware UTC; приводим к наивному для сравнения
        msg_date = msg.date.replace(tzinfo=None)
        if msg_date < since:
            break
        # реакции
        reactions_total = 0
        if msg.reactions and msg.reactions.results:
            reactions_total = sum(int(r.count or 0) for r in msg.reactions.results)
        # комментарии (replies)
        comments_total = 0
        if getattr(msg, "replies", None):
            comments_total = int(msg.replies.replies or 0)
        text = (msg.message or "")[:1000]
        link = f"https://t.me/{username}/{msg.id}"
        posts.append({
            "message_id": int(msg.id),
            "published_at": msg_date,
            "text": text,
            "views": int(msg.views or 0),
            "forwards": int(msg.forwards or 0),
            "reactions": reactions_total,
            "comments": comments_total,
            "link": link,
        })

    return {
        "channel_id": ch.id,
        "ok": True,
        "subscribers": subscribers,
        "posts": posts,
    }


def _upsert_channel_data(db: Session, channel_id: int, subscribers: int, posts: List[Dict[str, Any]]):
    """Тот же upsert что в /api/stats/tg/sync/push - чтобы UI работал одинаково."""
    for p in posts:
        existing = db.query(ChannelPost).filter(
            ChannelPost.channel_id == channel_id,
            ChannelPost.message_id == p["message_id"],
        ).first()
        if existing:
            existing.text = p["text"]
            existing.published_at = p["published_at"]
            existing.views = p["views"]
            existing.forwards = p["forwards"]
            existing.reactions = p["reactions"]
            existing.comments = p["comments"]
            existing.link = p["link"]
            existing.updated_at = datetime.now()
        else:
            db.add(ChannelPost(
                channel_id=channel_id,
                message_id=p["message_id"],
                text=p["text"],
                published_at=p["published_at"],
                views=p["views"],
                forwards=p["forwards"],
                reactions=p["reactions"],
                comments=p["comments"],
                link=p["link"],
                updated_at=datetime.now(),
            ))

    if posts:
        n = len(posts)
        avg_v = sum(p["views"] for p in posts) // n
        avg_l = sum(p["reactions"] for p in posts) // n
        avg_r = sum(p["forwards"] for p in posts) // n
        avg_c = sum(p["comments"] for p in posts) // n
    else:
        avg_v = avg_l = avg_r = avg_c = 0

    db.add(ChannelSnapshot(
        channel_id=channel_id,
        captured_at=datetime.now(),
        subscribers=subscribers,
        avg_views=avg_v,
        avg_likes=avg_l,
        avg_reposts=avg_r,
        avg_comments=avg_c,
        posts_total=len(posts),
    ))


async def collect_all_tg_channels(db: Session, period_days: int = 30) -> Dict[str, Any]:
    """Главная точка входа. Цепляется к TG, собирает все активные TG-каналы,
    upsert'ит посты, создаёт снапшоты. Возвращает сводку по каналам."""
    if not is_configured():
        return {"ok": False, "error": "Telethon не настроен (API_ID/HASH/SESSION_STRING)"}

    from telethon import TelegramClient
    from telethon.sessions import StringSession

    channels = db.query(Channel).filter(
        Channel.platform == Platform.tg,
        Channel.is_active == True,
    ).all()
    if not channels:
        return {"ok": True, "channels": [], "message": "Нет активных TG-каналов"}

    proxy = _proxy_tuple()
    client = TelegramClient(
        StringSession(settings.telethon_session_string),
        settings.telethon_api_id,
        settings.telethon_api_hash,
        proxy=proxy,
    )

    summary: List[Dict[str, Any]] = []
    try:
        await client.connect()
        if not await client.is_user_authorized():
            return {"ok": False, "error": "Telethon-сессия невалидна, перегенерируй gen_session"}

        for ch in channels:
            res = await _collect_one(client, ch, period_days)
            if res.get("ok"):
                _upsert_channel_data(db, ch.id, res["subscribers"], res["posts"])
                summary.append({
                    "channel_id": ch.id,
                    "name": ch.name,
                    "ok": True,
                    "subscribers": res["subscribers"],
                    "posts": len(res["posts"]),
                })
            else:
                summary.append({
                    "channel_id": ch.id,
                    "name": ch.name,
                    "ok": False,
                    "error": res.get("error"),
                })
        db.commit()
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass

    return {"ok": True, "channels": summary}
