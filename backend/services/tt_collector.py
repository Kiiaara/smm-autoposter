"""Сбор статистики TikTok-каналов.

Стратегия: две попытки подряд.
1. Primary: TikTokApi (питон + Playwright) - эмулирует браузер, самое надёжное.
2. Fallback: HTML-парсинг через httpx - вытаскивает SIGI_STATE из HTML профиля.

Из РФ ходим через xray (TG_PROXY_URL). Данные пишутся в те же таблицы
что и TG - channel_posts + channel_snapshots.
"""
import asyncio
import json
import logging
import re
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

import httpx
from sqlalchemy.orm import Session

from config import settings
from models.channel import Channel, Platform
from models.stats import ChannelPost, ChannelSnapshot

log = logging.getLogger("tt_collector")


def _channel_username(ch: Channel) -> Optional[str]:
    cfg = ch.config_json or {}
    raw = (cfg.get("username") or cfg.get("channel") or "").strip()
    if not raw:
        return None
    if "tiktok.com/@" in raw:
        raw = raw.split("tiktok.com/@", 1)[1]
    raw = raw.lstrip("@").strip("/").split("/")[0].split("?")[0]
    return raw or None


def _httpx_kwargs(timeout: int = 30) -> Dict:
    """Прокси через xray - тот же что для TG."""
    from publishers.telegram import _httpx_kwargs as tg_httpx_kwargs
    return tg_httpx_kwargs(timeout)


async def _collect_via_html(username: str, period_days: int) -> Dict[str, Any]:
    """Fallback-парсер через HTML профиля TT.
    Достаёт JSON из <script id="__UNIVERSAL_DATA_FOR_REHYDRATION__">."""
    url = f"https://www.tiktok.com/@{username}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        async with httpx.AsyncClient(**_httpx_kwargs(30), follow_redirects=True) as client:
            r = await client.get(url, headers=headers)
    except Exception as e:
        return {"ok": False, "error": f"http fetch: {e}"}

    if r.status_code != 200:
        return {"ok": False, "error": f"http {r.status_code}"}

    html = r.text
    m = re.search(
        r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.+?)</script>',
        html, re.DOTALL,
    )
    if not m:
        return {"ok": False, "error": "no __UNIVERSAL_DATA__ in HTML"}

    try:
        data = json.loads(m.group(1))
    except Exception as e:
        return {"ok": False, "error": f"json parse: {e}"}

    default = data.get("__DEFAULT_SCOPE__") or {}
    user_detail = default.get("webapp.user-detail") or {}
    user_info = user_detail.get("userInfo") or {}
    user = user_info.get("user") or {}
    stats = user_info.get("stats") or user_info.get("statsV2") or {}

    subscribers = int(stats.get("followerCount") or 0)

    # Список видео в HTML лежит в item-list или postList. Иногда есть, иногда нет -
    # тогда посты не соберём (нужен TikTokApi). Проверим оба места.
    item_list = default.get("webapp.item-list") or {}
    items = item_list.get("itemList") or []

    since = datetime.now() - timedelta(days=period_days)
    posts: List[Dict[str, Any]] = []
    for it in items:
        create_time = int(it.get("createTime") or 0)
        if not create_time:
            continue
        pub_dt = datetime.fromtimestamp(create_time)
        if pub_dt < since:
            continue
        st = it.get("stats") or {}
        posts.append({
            "message_id": int(it.get("id") or 0),
            "published_at": pub_dt,
            "text": (it.get("desc") or "")[:1000],
            "views": int(st.get("playCount") or 0),
            "forwards": int(st.get("shareCount") or 0),
            "reactions": int(st.get("diggCount") or 0),
            "comments": int(st.get("commentCount") or 0),
            "link": f"https://www.tiktok.com/@{username}/video/{it.get('id')}",
        })

    return {
        "ok": True,
        "subscribers": subscribers,
        "posts": posts,
        "source": "html",
    }


async def _collect_via_tiktokapi(username: str, period_days: int) -> Dict[str, Any]:
    """Основной путь - через либу TikTokApi (playwright)."""
    try:
        from TikTokApi import TikTokApi
    except ImportError:
        return {"ok": False, "error": "TikTokApi not installed"}

    proxy_url = settings.tg_proxy_url or None
    proxies = [proxy_url] if proxy_url else None

    try:
        async with TikTokApi() as api:
            await api.create_sessions(num_sessions=1, sleep_after=3, proxies=proxies)
            user = api.user(username)
            info = await user.info()

            stats = (info.get("userInfo") or {}).get("stats") or {}
            subscribers = int(stats.get("followerCount") or 0)

            since = datetime.now() - timedelta(days=period_days)
            posts: List[Dict[str, Any]] = []
            async for video in user.videos(count=100):
                v = video.as_dict
                create_time = int(v.get("createTime") or 0)
                if not create_time:
                    continue
                pub_dt = datetime.fromtimestamp(create_time)
                if pub_dt < since:
                    break
                st = v.get("stats") or {}
                posts.append({
                    "message_id": int(v.get("id") or 0),
                    "published_at": pub_dt,
                    "text": (v.get("desc") or "")[:1000],
                    "views": int(st.get("playCount") or 0),
                    "forwards": int(st.get("shareCount") or 0),
                    "reactions": int(st.get("diggCount") or 0),
                    "comments": int(st.get("commentCount") or 0),
                    "link": f"https://www.tiktok.com/@{username}/video/{v.get('id')}",
                })

            return {
                "ok": True,
                "subscribers": subscribers,
                "posts": posts,
                "source": "tiktokapi",
            }
    except Exception as e:
        return {"ok": False, "error": f"TikTokApi: {e}"}


def _upsert_channel_data(db: Session, channel_id: int, subscribers: int, posts: List[Dict[str, Any]]):
    """Тот же upsert что в TG-сборщике."""
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


async def collect_all_tt_channels(db: Session, period_days: int = 30) -> Dict[str, Any]:
    """Собирает все активные TT-каналы. Пробует TikTokApi, при неудаче - HTML fallback."""
    channels = db.query(Channel).filter(
        Channel.platform == Platform.tt,
        Channel.is_active == True,
    ).all()
    if not channels:
        return {"ok": True, "channels": [], "message": "Нет активных TikTok-каналов"}

    summary: List[Dict[str, Any]] = []
    for ch in channels:
        username = _channel_username(ch)
        if not username:
            summary.append({
                "channel_id": ch.id, "name": ch.name,
                "ok": False, "error": "no username in config",
            })
            continue

        # 1. primary: TikTokApi
        res = await _collect_via_tiktokapi(username, period_days)
        # 2. fallback: HTML
        if not res.get("ok"):
            log.warning(f"TT {username}: primary failed ({res.get('error')}), trying HTML")
            res = await _collect_via_html(username, period_days)

        if res.get("ok"):
            _upsert_channel_data(db, ch.id, res["subscribers"], res["posts"])
            summary.append({
                "channel_id": ch.id,
                "name": ch.name,
                "ok": True,
                "subscribers": res["subscribers"],
                "posts": len(res["posts"]),
                "source": res.get("source"),
            })
        else:
            summary.append({
                "channel_id": ch.id, "name": ch.name,
                "ok": False, "error": res.get("error"),
            })

    db.commit()
    return {"ok": True, "channels": summary}
