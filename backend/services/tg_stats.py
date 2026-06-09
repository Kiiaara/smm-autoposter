"""Сбор статистики из TG-каналов через Pyrogram (MTProto как юзер).

Bot API не отдаёт views/reactions постов - идём через user-сессию.
Pyrogram нормально работает с FakeTLS-секретами MTProxy (в отличие от Telethon 1.36).
Хранит session как string (TELETHON_SESSION_STRING - оставлено имя env для обратной совместимости).
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional

from pyrogram import Client
from pyrogram.errors import RPCError
from sqlalchemy.orm import Session

from config import settings
from models.channel import Channel
from models.post import PostTarget
from models.stats import ChannelSnapshot, PostStats

log = logging.getLogger("tg_stats")

_client: Optional[Client] = None
_client_lock: Optional[asyncio.Lock] = None


def is_configured() -> bool:
    return bool(
        settings.telethon_api_id
        and settings.telethon_api_hash
        and settings.telethon_session_string
    )


def _build_client_kwargs() -> dict:
    """Опции клиента: api_id/api_hash + опционально MTProxy."""
    kwargs: dict = {
        "name": "smm_tg_stats",
        "api_id": settings.telethon_api_id,
        "api_hash": settings.telethon_api_hash,
        "session_string": settings.telethon_session_string,
        "in_memory": True,
        "no_updates": True,  # нам не нужны updates, только запросы
    }
    if settings.telethon_mtproxy_host and settings.telethon_mtproxy_port and settings.telethon_mtproxy_secret:
        kwargs["proxy"] = {
            "scheme": "mtproxy",
            "hostname": settings.telethon_mtproxy_host,
            "port": settings.telethon_mtproxy_port,
            "secret": settings.telethon_mtproxy_secret,
        }
    elif settings.telethon_proxy_host and settings.telethon_proxy_port:
        kwargs["proxy"] = {
            "scheme": "socks5",
            "hostname": settings.telethon_proxy_host,
            "port": settings.telethon_proxy_port,
        }
    return kwargs


async def _get_client() -> Client:
    global _client, _client_lock
    if _client_lock is None:
        _client_lock = asyncio.Lock()
    async with _client_lock:
        if _client is None:
            _client = Client(**_build_client_kwargs())
        if not _client.is_connected:
            await _client.start()
    return _client


def _chat_id_arg(chat_id: str):
    """Pyrogram принимает '@username', int (для каналов -100...), или просто число."""
    chat_id = chat_id.strip()
    if chat_id.startswith("@"):
        return chat_id
    try:
        return int(chat_id)
    except ValueError:
        return chat_id


async def collect_tg_post_stats(target: PostTarget, db: Session):
    """Тянет views/forwards/reactions для конкретного TG-поста."""
    if not is_configured():
        return
    ch = target.channel
    cfg = ch.config_json or {}
    chat_id = cfg.get("chat_id", "")
    if not chat_id or not target.published_message_id:
        return

    try:
        client = await _get_client()
        msg_id = int(target.published_message_id)
        msg = await client.get_messages(_chat_id_arg(chat_id), msg_id)
        if not msg:
            return

        reactions_total = 0
        if msg.reactions and msg.reactions.reactions:
            reactions_total = sum(r.count for r in msg.reactions.reactions)

        # комменты - replies.replies если discussion group привязана
        comments = msg.replies.replies if msg.replies else 0

        stats = PostStats(
            post_target_id=target.id,
            captured_at=datetime.now(),
            views=msg.views or 0,
            likes=reactions_total,
            reposts=msg.forwards or 0,
            comments=comments,
            reactions=reactions_total,
        )
        db.add(stats)
    except RPCError as e:
        log.warning(f"TG post stats failed for target {target.id}: {e}")
    except Exception as e:
        log.warning(f"TG post stats error for target {target.id}: {e}")


async def collect_tg_channel_avg(channel: Channel, db: Session):
    """Подписчики + средние метрики по последним 100 постам канала."""
    if not is_configured():
        return
    cfg = channel.config_json or {}
    chat_id = cfg.get("chat_id", "")
    if not chat_id:
        return

    try:
        client = await _get_client()
        entity = await client.get_chat(_chat_id_arg(chat_id))
        subscribers = entity.members_count or 0

        # последние 100 постов
        avg_views = avg_likes = avg_reposts = avg_comments = 0
        posts_total = 0
        try:
            msgs = []
            async for m in client.get_chat_history(_chat_id_arg(chat_id), limit=100):
                if m and (m.text or m.caption or m.media):
                    msgs.append(m)
            posts_total = len(msgs)
            if posts_total > 0:
                views_sum = sum((m.views or 0) for m in msgs)
                reposts_sum = sum((m.forwards or 0) for m in msgs)
                likes_sum = sum(
                    sum(r.count for r in m.reactions.reactions)
                    if (m.reactions and m.reactions.reactions) else 0
                    for m in msgs
                )
                comments_sum = sum((m.replies.replies if m.replies else 0) for m in msgs)
                avg_views = views_sum // posts_total
                avg_likes = likes_sum // posts_total
                avg_reposts = reposts_sum // posts_total
                avg_comments = comments_sum // posts_total
        except Exception as e:
            log.warning(f"TG messages fetch failed for {channel.name}: {e}")

        snap = ChannelSnapshot(
            channel_id=channel.id,
            captured_at=datetime.now(),
            subscribers=subscribers,
            avg_views=avg_views,
            avg_likes=avg_likes,
            avg_reposts=avg_reposts,
            avg_comments=avg_comments,
            posts_total=posts_total,
        )
        db.add(snap)
    except RPCError as e:
        log.warning(f"TG snapshot failed for {channel.name}: {e}")
    except Exception as e:
        log.warning(f"TG snapshot error for {channel.name}: {e}")
