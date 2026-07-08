from datetime import datetime, timedelta
from typing import List
import httpx
from sqlalchemy.orm import Session
from database import SessionLocal
from models.post import Post, PostTarget, PostTargetStatus
from models.channel import Channel, Platform
from models.stats import PostStats, ChannelSnapshot, ChannelPost

VK_API = "https://api.vk.com/method"


async def _vk(method: str, params: dict, token: str, version: str = "5.131") -> dict:
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(f"{VK_API}/{method}", params={
            **params, "access_token": token, "v": version,
        })
    return r.json()


async def collect_vk_post_stats(target: PostTarget, db: Session):
    """Fetch VK post metrics and save snapshot."""
    ch = target.channel
    cfg = ch.config_json or {}
    token = cfg.get("access_token", "")
    owner_id = cfg.get("owner_id", "")
    if not token or not owner_id or not target.published_message_id:
        return

    post_ref = f"{owner_id}_{target.published_message_id}"
    r = await _vk("wall.getById", {"posts": post_ref}, token, cfg.get("version", "5.131"))
    if "response" not in r or not r["response"]:
        return

    p = r["response"][0]
    stats = PostStats(
        post_target_id=target.id,
        captured_at=datetime.now(),
        views=p.get("views", {}).get("count", 0),
        likes=p.get("likes", {}).get("count", 0),
        reposts=p.get("reposts", {}).get("count", 0),
        comments=p.get("comments", {}).get("count", 0),
        reactions=p.get("reaction", {}).get("count", 0) if isinstance(p.get("reaction"), dict) else 0,
    )
    db.add(stats)


async def collect_vk_channel_subs(channel: Channel, db: Session):
    """Подписчики + агрегаты по всему каналу (последние 100 постов)."""
    cfg = channel.config_json or {}
    token = cfg.get("access_token", "")
    owner_id = cfg.get("owner_id", "")
    if not token or not owner_id:
        return
    version = cfg.get("version", "5.131")

    group_id = str(owner_id).lstrip("-")

    # 1. подписчики. Параметр называется group_ids (мн. число) - иначе VK возвращает пустой ответ.
    r = await _vk("groups.getById", {
        "group_ids": group_id,
        "fields": "members_count",
    }, token, version)

    members = 0
    if "response" in r:
        groups = r["response"].get("groups") if isinstance(r["response"], dict) else r["response"]
        if groups and len(groups) > 0:
            members = groups[0].get("members_count", 0)

    # 2. последние 100 постов канала - средние метрики + upsert каждого поста в channel_posts
    # (чтобы работали общие расчёты по каналу как для TG/TT - все посты, не только через сервис)
    avg_views = avg_likes = avg_reposts = avg_comments = 0
    posts_total = 0
    try:
        wall = await _vk("wall.get", {
            "owner_id": owner_id,
            "count": 100,
            "filter": "owner",
        }, token, version)
        items = wall.get("response", {}).get("items", [])
        # игнорируем закреплённые повторы и пустые
        posts = [p for p in items if not p.get("is_pinned") or len(items) <= 1]
        posts_total = len(posts)
        if posts_total > 0:
            avg_views = sum(p.get("views", {}).get("count", 0) for p in posts) // posts_total
            avg_likes = sum(p.get("likes", {}).get("count", 0) for p in posts) // posts_total
            avg_reposts = sum(p.get("reposts", {}).get("count", 0) for p in posts) // posts_total
            avg_comments = sum(p.get("comments", {}).get("count", 0) for p in posts) // posts_total

        # Upsert каждого поста в channel_posts - чтобы "По каналам за период" видела ВСЕ посты,
        # а не только через наш сервис. Ключ: (channel_id, message_id).
        # VK: у поста есть id (в рамках стены группы). Ссылка: vk.com/wall{owner_id}_{id}
        owner_str = str(owner_id)
        for p in posts:
            msg_id = p.get("id")
            if not msg_id:
                continue
            date_ts = p.get("date")  # unix ts
            if not date_ts:
                continue
            pub_dt = datetime.fromtimestamp(int(date_ts))
            text = (p.get("text") or "")[:1000]
            views = p.get("views", {}).get("count", 0)
            likes = p.get("likes", {}).get("count", 0)
            reposts = p.get("reposts", {}).get("count", 0)
            comments = p.get("comments", {}).get("count", 0)
            link = f"https://vk.com/wall{owner_str}_{msg_id}"

            existing = db.query(ChannelPost).filter(
                ChannelPost.channel_id == channel.id,
                ChannelPost.message_id == int(msg_id),
            ).first()
            if existing:
                existing.text = text
                existing.published_at = pub_dt
                existing.views = views
                existing.forwards = reposts
                existing.reactions = likes
                existing.comments = comments
                existing.link = link
                existing.updated_at = datetime.now()
            else:
                db.add(ChannelPost(
                    channel_id=channel.id,
                    message_id=int(msg_id),
                    text=text,
                    published_at=pub_dt,
                    views=views,
                    forwards=reposts,
                    reactions=likes,
                    comments=comments,
                    link=link,
                    updated_at=datetime.now(),
                ))
            db.flush()
    except Exception as e:
        print(f"[stats] vk wall.get failed for {channel.name}: {e}")

    snap = ChannelSnapshot(
        channel_id=channel.id,
        captured_at=datetime.now(),
        subscribers=members,
        avg_views=avg_views,
        avg_likes=avg_likes,
        avg_reposts=avg_reposts,
        avg_comments=avg_comments,
        posts_total=posts_total,
    )
    db.add(snap)


async def collect_tg_channel_subs(channel: Channel, db: Session):
    """Снапшот TG-канала. Если Telethon настроен - тянем полный набор метрик
    (подписчики + средние views/likes/reposts/comments). Иначе fallback на Bot API
    (только member count)."""
    from services import tg_stats
    if tg_stats.is_configured():
        await tg_stats.collect_tg_channel_avg(channel, db)
        return

    # fallback: только подписчики через Bot API
    cfg = channel.config_json or {}
    token = cfg.get("bot_token", "")
    chat_id = cfg.get("chat_id", "")
    if not token or not chat_id:
        return

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            f"https://api.telegram.org/bot{token}/getChatMemberCount",
            params={"chat_id": chat_id},
        )
    data = r.json()
    if not data.get("ok"):
        return

    snap = ChannelSnapshot(
        channel_id=channel.id,
        captured_at=datetime.now(),
        subscribers=data["result"],
    )
    db.add(snap)


async def run_post_stats_collection():
    """Update metrics for posts published in the last 7 days."""
    db: Session = SessionLocal()
    try:
        cutoff = datetime.now() - timedelta(days=7)
        targets = db.query(PostTarget).filter(
            PostTarget.status == PostTargetStatus.published,
            PostTarget.published_at >= cutoff,
        ).all()

        from services import tg_stats
        for t in targets:
            if not t.channel:
                continue
            try:
                if t.channel.platform == Platform.vk:
                    await collect_vk_post_stats(t, db)
                elif t.channel.platform == Platform.tg and tg_stats.is_configured():
                    await tg_stats.collect_tg_post_stats(t, db)
            except Exception as e:
                print(f"Failed to collect stats for target {t.id}: {e}")
        db.commit()
    finally:
        db.close()


async def run_subscribers_collection():
    """Snapshot subscriber counts for all active channels."""
    db: Session = SessionLocal()
    try:
        channels = db.query(Channel).filter(Channel.is_active == True).all()
        for ch in channels:
            try:
                if ch.platform == Platform.vk:
                    await collect_vk_channel_subs(ch, db)
                elif ch.platform == Platform.tg:
                    await collect_tg_channel_subs(ch, db)
            except Exception as e:
                print(f"Failed to snapshot {ch.id} ({ch.platform}): {e}")
        db.commit()
    finally:
        db.close()
