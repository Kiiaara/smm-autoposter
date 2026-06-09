"""Сбор статистики из TG-каналов через Telethon (MTProto, читаем как юзер).

Bot API не отдаёт views/reactions постов, поэтому идём через user-сессию.
Один глобальный клиент с StringSession - переподключается при необходимости.
"""
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import Channel as TLChannel, Message

from config import settings
from models.channel import Channel
from models.post import PostTarget
from models.stats import ChannelSnapshot, PostStats

log = logging.getLogger("tg_stats")

_client: Optional[TelegramClient] = None
_client_lock = None  # asyncio.Lock - создадим лениво


def is_configured() -> bool:
    return bool(settings.telethon_api_id and settings.telethon_api_hash and settings.telethon_session_string)


def _build_proxy():
    """Если в .env задан SOCKS5 - возвращаем tuple для Telethon, иначе None."""
    if settings.telethon_proxy_host and settings.telethon_proxy_port:
        import socks
        return (socks.SOCKS5, settings.telethon_proxy_host, settings.telethon_proxy_port)
    return None


async def _get_client() -> TelegramClient:
    """Возвращает (и при необходимости создаёт + коннектит) глобальный клиент."""
    global _client, _client_lock
    if _client_lock is None:
        import asyncio
        _client_lock = asyncio.Lock()
    async with _client_lock:
        if _client is None:
            _client = TelegramClient(
                StringSession(settings.telethon_session_string),
                settings.telethon_api_id,
                settings.telethon_api_hash,
                proxy=_build_proxy(),
            )
        if not _client.is_connected():
            await _client.connect()
        if not await _client.is_user_authorized():
            log.error("Telethon session не авторизована - пересоздай session_string")
            raise RuntimeError("Telethon not authorized")
    return _client


def _chat_to_entity_arg(chat_id: str):
    """chat_id в БД может быть '@username', '-100123', '123' - всё это понимает Telethon."""
    chat_id = chat_id.strip()
    if chat_id.startswith("@"):
        return chat_id
    try:
        return int(chat_id)
    except ValueError:
        return chat_id


async def collect_tg_post_stats(target: PostTarget, db: Session):
    """Тянет views/forwards/reactions/comments_count для конкретного TG-поста.
    target.published_message_id - id сообщения в канале."""
    if not is_configured():
        return
    ch = target.channel
    cfg = ch.config_json or {}
    chat_id = cfg.get("chat_id", "")
    if not chat_id or not target.published_message_id:
        return

    try:
        client = await _get_client()
        entity = await client.get_entity(_chat_to_entity_arg(chat_id))
        msg_id = int(target.published_message_id)
        msgs = await client.get_messages(entity, ids=[msg_id])
        if not msgs or msgs[0] is None:
            return
        m: Message = msgs[0]

        # реакции суммарно
        reactions_total = 0
        if m.reactions and m.reactions.results:
            reactions_total = sum(r.count for r in m.reactions.results)

        # комментарии - replies.replies (если discussion group привязана)
        comments = 0
        if m.replies:
            comments = m.replies.replies or 0

        stats = PostStats(
            post_target_id=target.id,
            captured_at=datetime.now(),
            views=m.views or 0,
            likes=reactions_total,
            reposts=m.forwards or 0,
            comments=comments,
            reactions=reactions_total,
        )
        db.add(stats)
    except Exception as e:
        log.warning(f"TG post stats failed for target {target.id}: {e}")


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
        entity = await client.get_entity(_chat_to_entity_arg(chat_id))

        # участники
        subscribers = 0
        try:
            from telethon.tl.functions.channels import GetFullChannelRequest
            full = await client(GetFullChannelRequest(entity))
            subscribers = full.full_chat.participants_count or 0
        except Exception as e:
            log.warning(f"GetFullChannel failed for {channel.name}: {e}")

        # средние по последним 100 постам
        avg_views = avg_likes = avg_reposts = avg_comments = 0
        posts_total = 0
        try:
            msgs = await client.get_messages(entity, limit=100)
            real_posts = [m for m in msgs if m and (m.message or m.media)]
            posts_total = len(real_posts)
            if posts_total > 0:
                views_sum = sum((m.views or 0) for m in real_posts)
                reposts_sum = sum((m.forwards or 0) for m in real_posts)
                likes_sum = sum(
                    sum(r.count for r in m.reactions.results)
                    if (m.reactions and m.reactions.results) else 0
                    for m in real_posts
                )
                comments_sum = sum((m.replies.replies if m.replies else 0) for m in real_posts)
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
    except Exception as e:
        log.warning(f"TG channel snapshot failed for {channel.name}: {e}")
