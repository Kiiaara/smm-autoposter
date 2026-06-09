"""Сбор статистики из TG-каналов через TGStat API (api.tgstat.ru).

Бесплатный тариф: 2 канала на токен, ~500 запросов/день. Метрики не realtime
(обновляются у TGStat раз в несколько часов), но достаточны для топ-постов и
динамики подписчиков.

Каналы привязываются к TGStat по @username, который кладётся в Channel.config_json:
  config_json["username"] = "travociv"  (без @)
"""
import logging
from datetime import datetime
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from config import settings
from models.channel import Channel
from models.post import PostTarget
from models.stats import ChannelSnapshot, PostStats

log = logging.getLogger("tg_stats")

TGSTAT_API = "https://api.tgstat.ru"
TIMEOUT = 15


def is_configured() -> bool:
    return bool(settings.tgstat_token)


def _channel_username(ch: Channel) -> Optional[str]:
    """Из config_json вытаскиваем username канала для TGStat (без @).
    Источник: поле 'channel' (например '@travociv' или 'https://t.me/travociv'),
    либо явное 'username'/'tgstat_username'."""
    cfg = ch.config_json or {}
    raw = (
        cfg.get("username")
        or cfg.get("tgstat_username")
        or cfg.get("channel")
        or ""
    ).strip()
    if not raw:
        return None
    # https://t.me/xxx
    if "t.me/" in raw:
        raw = raw.split("t.me/", 1)[1]
    # https://telegram.me/xxx
    if "telegram.me/" in raw:
        raw = raw.split("telegram.me/", 1)[1]
    # @username
    username = raw.lstrip("@").strip("/").split("/")[0]
    # отсекаем приватные ссылки (joinchat, +HASH) - они не публичные, TGStat не сможет
    if username.startswith("+") or username.startswith("joinchat"):
        return None
    return username or None


async def _tgstat_get(path: str, params: dict) -> Optional[dict]:
    """GET к TGStat API. Возвращает payload или None при ошибке."""
    params = {**params, "token": settings.tgstat_token}
    url = f"{TGSTAT_API}/{path.lstrip('/')}"
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.get(url, params=params)
        data = r.json()
    except Exception as e:
        log.warning(f"TGStat {path} request failed: {e}")
        return None
    if data.get("status") != "ok":
        log.warning(f"TGStat {path} error: {data.get('error') or data}")
        return None
    return data.get("response")


async def collect_tg_post_stats(target: PostTarget, db: Session):
    """Тянет метрики конкретного поста через posts/get.
    postId = '@username/message_id', например 'travociv/12345'.
    """
    if not is_configured():
        return
    ch = target.channel
    username = _channel_username(ch)
    if not username or not target.published_message_id:
        return

    post_id = f"@{username}/{target.published_message_id}"
    resp = await _tgstat_get("posts/get", {"postId": post_id})
    if not resp:
        return

    # TGStat возвращает: views, forwards, reactions_count
    stats = PostStats(
        post_target_id=target.id,
        captured_at=datetime.now(),
        views=int(resp.get("views") or 0),
        likes=int(resp.get("reactions_count") or 0),
        reposts=int(resp.get("forwards") or 0),
        comments=int(resp.get("comments_count") or 0),
        reactions=int(resp.get("reactions_count") or 0),
    )
    db.add(stats)


async def fetch_channel_posts(channel: Channel, limit: int = 50, period_days: int = 30) -> list[dict]:
    """Тянет последние посты канала из TGStat для отображения в топе.
    Не пишет в БД - просто возвращает список словарей с метриками.
    Возвращает: [{message_id, text, date, views, forwards, reactions_count, comments_count, link}, ...]
    """
    if not is_configured():
        return []
    username = _channel_username(channel)
    if not username:
        return []
    from datetime import timedelta
    end = int(datetime.now().timestamp())
    start = int((datetime.now() - timedelta(days=period_days)).timestamp())
    resp = await _tgstat_get("channels/posts", {
        "channelId": f"@{username}",
        "limit": limit,
        "startTime": start,
        "endTime": end,
    })
    items = (resp or {}).get("items") or []
    return items


async def collect_tg_channel_avg(channel: Channel, db: Session):
    """Подписчики + средние метрики канала через channels/get + channels/posts."""
    if not is_configured():
        return
    username = _channel_username(channel)
    if not username:
        return

    # 1) инфа о канале (подписчики)
    info = await _tgstat_get("channels/get", {"channelId": f"@{username}"})
    if not info:
        return
    subscribers = int(info.get("participants_count") or 0)

    # 2) последние 50 постов канала - считаем средние
    posts_resp = await _tgstat_get("channels/posts", {"channelId": f"@{username}", "limit": 50})
    items = (posts_resp or {}).get("items") or []
    posts_total = len(items)

    avg_views = avg_likes = avg_reposts = avg_comments = 0
    if posts_total > 0:
        views_sum = sum(int(p.get("views") or 0) for p in items)
        likes_sum = sum(int(p.get("reactions_count") or 0) for p in items)
        reposts_sum = sum(int(p.get("forwards") or 0) for p in items)
        comments_sum = sum(int(p.get("comments_count") or 0) for p in items)
        avg_views = views_sum // posts_total
        avg_likes = likes_sum // posts_total
        avg_reposts = reposts_sum // posts_total
        avg_comments = comments_sum // posts_total

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
