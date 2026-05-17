from datetime import datetime
from typing import List, Dict
from sqlalchemy.orm import Session
from models.post import Post, PostTarget, PostStatus, PostTargetStatus
from models.channel import Platform
from models.reminder import Reminder
from publishers.telegram import publish_to_telegram, send_reminder
from publishers.vk import publish_to_vk
from publishers.instagram import publish_to_instagram
from publishers.max_ru import publish_to_max
from config import settings


async def publish_post(post: Post, db: Session) -> List[Dict]:
    results = []

    for target in post.targets:
        if target.status == PostTargetStatus.published:
            continue

        ch = target.channel
        cfg = ch.config_json or {}
        platform = ch.platform

        if platform == Platform.tg:
            result = await publish_to_telegram(
                bot_token=cfg.get("bot_token", ""),
                chat_id=cfg.get("chat_id", ""),
                text_raw=post.text_tg,
                text_ranges=post.text_tg_ranges or [],
                media_paths=post.media_paths or [],
                poll_json=post.poll_json,
            )
        elif platform == Platform.vk:
            result = await publish_to_vk(
                access_token=cfg.get("access_token", ""),
                owner_id=cfg.get("owner_id", ""),
                text_plain=post.text_plain,
                media_paths=post.media_paths or [],
                poll_json=post.poll_json,
                version=cfg.get("version", "5.131"),
            )
        elif platform == Platform.ig:
            result = await publish_to_instagram()
        else:
            result = await publish_to_max()

        target.status = PostTargetStatus.published if result.ok else PostTargetStatus.failed
        target.published_at = datetime.now() if result.ok else None
        target.published_message_id = result.message_id
        target.published_url = result.url
        target.error = result.error if not result.ok else None

        results.append({
            "channel_id": ch.id,
            "channel_name": ch.name,
            "platform": platform.value,
            "status": target.status.value,
            "url": result.url,
            "error": result.error,
        })

    # update post status
    statuses = [t.status for t in post.targets]
    if not statuses:
        # no targets to publish to - keep as failed
        post.status = PostStatus.failed
    elif any(s == PostTargetStatus.published for s in statuses):
        post.status = PostStatus.published
    else:
        post.status = PostStatus.failed

    db.commit()

    # пингуем юзера если есть упавшие таргеты
    if any(s == PostTargetStatus.failed for s in statuses):
        from services.reminder_service import send_publish_failure_alert
        await send_publish_failure_alert(post.id, post.title)

    return results
