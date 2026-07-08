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


TT_BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.tiktok.com/",
}


async def _collect_via_html(username: str, period_days: int) -> Dict[str, Any]:
    """HTML-парсер профиля TT. Достаёт JSON из __UNIVERSAL_DATA_FOR_REHYDRATION__.
    Даёт подписчиков + первую страницу видео (~30 штук)."""
    url = f"https://www.tiktok.com/@{username}"
    try:
        async with httpx.AsyncClient(**_httpx_kwargs(30), follow_redirects=True) as client:
            r = await client.get(url, headers=TT_BROWSER_HEADERS)
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
        return {"ok": False, "error": "no __UNIVERSAL_DATA__ (TT captcha/blocked?)"}

    try:
        data = json.loads(m.group(1))
    except Exception as e:
        return {"ok": False, "error": f"json parse: {e}"}

    default = data.get("__DEFAULT_SCOPE__") or {}
    user_detail = default.get("webapp.user-detail") or {}
    user_info = user_detail.get("userInfo") or {}
    stats = user_info.get("stats") or user_info.get("statsV2") or {}
    subscribers = int(stats.get("followerCount") or 0)

    # Список видео живёт в webapp.video-detail / webapp.item-list / user-post
    items = []
    for key in ("webapp.item-list", "webapp.user-post-list", "webapp.video-detail"):
        block = default.get(key) or {}
        candidate = block.get("itemList") or block.get("itemStruct") or []
        if isinstance(candidate, list) and candidate:
            items = candidate
            break
        if isinstance(candidate, dict):
            items = [candidate]
            break

    since = datetime.now() - timedelta(days=period_days)
    posts: List[Dict[str, Any]] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        create_time = int(it.get("createTime") or 0)
        if not create_time:
            continue
        pub_dt = datetime.fromtimestamp(create_time)
        if pub_dt < since:
            continue
        st = it.get("stats") or it.get("statsV2") or {}
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
        "sec_uid": (user_info.get("user") or {}).get("secUid"),
    }


async def _collect_via_web_api(username: str, sec_uid: str, period_days: int) -> Dict[str, Any]:
    """Дозагрузка постов через web-api TT. Работает если у нас есть secUid юзера
    (его отдаёт HTML). Тянем список постов постранично через post/item_list."""
    if not sec_uid:
        return {"ok": False, "error": "no sec_uid for api call"}

    since = datetime.now() - timedelta(days=period_days)
    posts: List[Dict[str, Any]] = []
    cursor = 0
    has_more = True
    pages = 0
    max_pages = 5  # ~150 видео

    async with httpx.AsyncClient(**_httpx_kwargs(30), follow_redirects=True) as client:
        while has_more and pages < max_pages:
            params = {
                "aid": "1988",
                "app_language": "en",
                "device_platform": "web",
                "secUid": sec_uid,
                "cursor": str(cursor),
                "count": "30",
            }
            try:
                r = await client.get(
                    "https://www.tiktok.com/api/post/item_list/",
                    params=params, headers=TT_BROWSER_HEADERS,
                )
                data = r.json()
            except Exception as e:
                log.warning(f"TT web-api page {pages}: {e}")
                break

            items = data.get("itemList") or []
            if not items:
                break
            oldest_in_page = None
            for it in items:
                create_time = int(it.get("createTime") or 0)
                if not create_time:
                    continue
                pub_dt = datetime.fromtimestamp(create_time)
                oldest_in_page = pub_dt if oldest_in_page is None else min(oldest_in_page, pub_dt)
                if pub_dt < since:
                    continue
                st = it.get("stats") or it.get("statsV2") or {}
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
            # если старейший пост в странице уже < since - дальше не листаем
            if oldest_in_page and oldest_in_page < since:
                break
            has_more = bool(data.get("hasMore"))
            cursor = int(data.get("cursor") or 0)
            pages += 1

    return {"ok": True, "posts": posts, "source": "web-api"}




def _upsert_channel_data(db: Session, channel_id: int, subscribers: int, posts: List[Dict[str, Any]]):
    """Upsert постов канала. Дедуплицируем внутри пачки - RapidAPI может отдавать
    одно и то же видео на разных страницах при листании."""
    seen: set = set()
    for p in posts:
        key = p["message_id"]
        if key in seen:
            continue
        seen.add(key)
        existing = db.query(ChannelPost).filter(
            ChannelPost.channel_id == channel_id,
            ChannelPost.message_id == key,
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
                message_id=key,
                text=p["text"],
                published_at=p["published_at"],
                views=p["views"],
                forwards=p["forwards"],
                reactions=p["reactions"],
                comments=p["comments"],
                link=p["link"],
                updated_at=datetime.now(),
            ))
        # flush чтобы следующая проверка "existing" увидела только что добавленный ряд
        db.flush()

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

        # Основной путь - RapidAPI. Если ключа нет - фолбэк на HTML (даст только подписчиков)
        if settings.rapidapi_tt_key:
            res = await _collect_via_rapidapi(username, period_days)
        else:
            res = await _collect_via_html(username, period_days)

        if not res.get("ok"):
            summary.append({
                "channel_id": ch.id, "name": ch.name,
                "ok": False, "error": res.get("error"),
            })
            continue

        _upsert_channel_data(db, ch.id, res["subscribers"], res["posts"])
        summary.append({
            "channel_id": ch.id,
            "name": ch.name,
            "ok": True,
            "subscribers": res["subscribers"],
            "posts": len(res["posts"]),
            "source": res.get("source"),
        })

    db.commit()
    return {"ok": True, "channels": summary}


async def _collect_via_rapidapi(username: str, period_days: int) -> Dict[str, Any]:
    """Сбор через RapidAPI TikTok API 23 - самый надёжный путь.
    Два запроса: /api/user/info (инфа + secUid) → /api/user/posts (список видео).
    Расход квоты: 1 + N страниц по 30 видео. Для 30 дней активного канала обычно 2-3 запроса."""
    api_headers = {
        "x-rapidapi-key": settings.rapidapi_tt_key,
        "x-rapidapi-host": settings.rapidapi_tt_host,
    }
    base = f"https://{settings.rapidapi_tt_host}"

    async with httpx.AsyncClient(**_httpx_kwargs(30)) as client:
        # 1. инфа юзера. Ходим через xray - RapidAPI режет по IP страны (РФ забанена)
        try:
            r = await client.get(f"{base}/api/user/info", params={"uniqueId": username}, headers=api_headers)
            info = r.json()
        except Exception as e:
            return {"ok": False, "error": f"user/info: {e}"}

        user_info = (info.get("userInfo") or {}) if isinstance(info, dict) else {}
        user = user_info.get("user") or {}
        stats = user_info.get("stats") or user_info.get("statsV2") or {}
        sec_uid = user.get("secUid") or user.get("sec_uid")
        subscribers = int(stats.get("followerCount") or 0)

        if not sec_uid:
            return {"ok": False, "error": f"no secUid in response: {str(info)[:200]}"}

        # 2. список постов постранично
        since = datetime.now() - timedelta(days=period_days)
        posts: List[Dict[str, Any]] = []
        cursor = 0
        max_pages = 5

        for page in range(max_pages):
            try:
                r = await client.get(
                    f"{base}/api/user/posts",
                    params={"secUid": sec_uid, "count": "30", "cursor": str(cursor)},
                    headers=api_headers,
                )
                data = r.json()
            except Exception as e:
                log.warning(f"TT rapidapi page {page}: {e}")
                break

            items = (data.get("data") or {}).get("itemList") or data.get("itemList") or []
            if not items:
                break

            oldest_in_page = None
            for it in items:
                if not isinstance(it, dict):
                    continue
                create_time = int(it.get("createTime") or 0)
                if not create_time:
                    continue
                pub_dt = datetime.fromtimestamp(create_time)
                oldest_in_page = pub_dt if oldest_in_page is None else min(oldest_in_page, pub_dt)
                if pub_dt < since:
                    continue
                st = it.get("stats") or it.get("statsV2") or {}
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

            if oldest_in_page and oldest_in_page < since:
                break
            has_more = bool((data.get("data") or {}).get("hasMore") or data.get("hasMore"))
            if not has_more:
                break
            cursor = int((data.get("data") or {}).get("cursor") or data.get("cursor") or 0)

    return {"ok": True, "subscribers": subscribers, "posts": posts, "source": "rapidapi"}
