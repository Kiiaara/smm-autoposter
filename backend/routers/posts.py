from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models.post import Post, PostTarget, PostStatus, PostTargetStatus
from models.channel import Channel
from schemas.post import PostCreate, PostUpdate, PostRead, PostListItem

router = APIRouter(prefix="/api/posts", tags=["posts"])


def _build_list_item(post: Post) -> PostListItem:
    platforms = list({t.channel.platform.value for t in post.targets if t.channel})
    if post.text_tg_html:
        from publishers.html_sanitize import html_to_plain
        preview = html_to_plain(post.text_tg_html)[:120]
    else:
        preview = (post.text_tg or post.text_plain or "")[:120]
    return PostListItem(
        id=post.id,
        title=post.title,
        status=post.status,
        scheduled_at=post.scheduled_at,
        created_at=post.created_at,
        platforms=platforms,
        preview_text=preview,
    )


@router.get("", response_model=List[PostListItem])
def list_posts(
    status: Optional[str] = None,
    week_start: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(Post)
    if status:
        q = q.filter(Post.status == status)
    if week_start:
        try:
            ws = datetime.strptime(week_start, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(400, "week_start must be YYYY-MM-DD")
        from datetime import timedelta
        we = ws + timedelta(days=7)
        q = q.filter(Post.scheduled_at >= ws, Post.scheduled_at < we)
    posts = q.order_by(Post.scheduled_at.asc().nullslast(), Post.created_at.desc()).all()
    return [_build_list_item(p) for p in posts]


@router.post("", response_model=PostRead, status_code=201)
def create_post(data: PostCreate, db: Session = Depends(get_db)):
    post = Post(
        title=data.title,
        text_tg_html=data.text_tg_html,
        text_tg=data.text_tg,
        text_tg_ranges=[r.model_dump() for r in data.text_tg_ranges],
        text_plain=data.text_plain,
        media_paths=data.media_paths,
        poll_json=data.poll_json.model_dump() if data.poll_json else None,
        status=data.status,
        scheduled_at=data.scheduled_at,
    )
    db.add(post)
    db.flush()

    for t in data.targets:
        ch = db.get(Channel, t.channel_id)
        if not ch:
            raise HTTPException(400, f"Channel {t.channel_id} not found")
        db.add(PostTarget(post_id=post.id, channel_id=t.channel_id))

    db.commit()
    db.refresh(post)
    return post


@router.get("/{post_id}", response_model=PostRead)
def get_post(post_id: int, db: Session = Depends(get_db)):
    post = db.get(Post, post_id)
    if not post:
        raise HTTPException(404, "Post not found")
    return post


@router.patch("/{post_id}", response_model=PostRead)
def update_post(post_id: int, data: PostUpdate, db: Session = Depends(get_db)):
    post = db.get(Post, post_id)
    if not post:
        raise HTTPException(404, "Post not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        if field == "targets":
            # replace targets
            for t in post.targets:
                db.delete(t)
            db.flush()
            for t in (value or []):
                db.add(PostTarget(post_id=post.id, channel_id=t["channel_id"]))
        elif field == "text_tg_ranges":
            post.text_tg_ranges = [r.model_dump() if hasattr(r, "model_dump") else r for r in (value or [])]
        elif field == "poll_json":
            post.poll_json = value.model_dump() if hasattr(value, "model_dump") else value
        else:
            setattr(post, field, value)

    post.updated_at = datetime.now()
    db.commit()
    db.refresh(post)
    return post


@router.delete("/{post_id}")
def delete_post(post_id: int, db: Session = Depends(get_db)):
    post = db.get(Post, post_id)
    if not post:
        raise HTTPException(404, "Post not found")
    db.delete(post)
    db.commit()
    return {"ok": True}


@router.post("/{post_id}/publish")
async def publish_now(post_id: int, db: Session = Depends(get_db)):
    from services.publish_service import publish_post
    post = db.get(Post, post_id)
    if not post:
        raise HTTPException(404, "Post not found")
    results = await publish_post(post, db)
    return {"results": results}
