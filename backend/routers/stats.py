from datetime import datetime, timedelta
from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from pydantic import BaseModel
from database import get_db
from models.post import Post, PostTarget, PostTargetStatus
from models.channel import Channel, Platform
from models.stats import PostStats, ChannelSnapshot

router = APIRouter(prefix="/api/stats", tags=["stats"])


class TopPostItem(BaseModel):
    post_id: int
    title: Optional[str]
    preview: Optional[str]
    platform: str
    channel_name: str
    published_at: datetime
    url: Optional[str]
    views: int
    likes: int
    reposts: int
    comments: int


class ChannelSummary(BaseModel):
    channel_id: int
    name: str
    platform: str
    subscribers: int
    avg_views: int
    avg_likes: int
    posts_count: int


class SubscriberPoint(BaseModel):
    date: str
    subscribers: int


class SubscriberSeries(BaseModel):
    channel_id: int
    name: str
    platform: str
    points: List[SubscriberPoint]


class BestTimeCell(BaseModel):
    day_of_week: int  # 0=Mon, 6=Sun
    hour: int
    avg_views: float
    posts: int


class OverviewResponse(BaseModel):
    total_posts: int
    total_views: int
    total_likes: int
    total_comments: int
    channels: List[ChannelSummary]


def _latest_stats_subquery(db: Session):
    """Return mapping post_target_id -> latest PostStats."""
    latest = db.query(
        PostStats.post_target_id,
        func.max(PostStats.captured_at).label("max_t"),
    ).group_by(PostStats.post_target_id).subquery()

    rows = db.query(PostStats).join(
        latest,
        (PostStats.post_target_id == latest.c.post_target_id) &
        (PostStats.captured_at == latest.c.max_t),
    ).all()
    return {r.post_target_id: r for r in rows}


@router.get("/overview", response_model=OverviewResponse)
def overview(period_days: int = 30, db: Session = Depends(get_db)):
    since = datetime.now() - timedelta(days=period_days)

    # тоталы по нашим постам (за период)
    targets = db.query(PostTarget).filter(
        PostTarget.status == PostTargetStatus.published,
        PostTarget.published_at >= since,
    ).all()
    latest = _latest_stats_subquery(db)
    total_views = total_likes = total_comments = 0
    posts_per_channel: Dict[int, int] = {}
    for t in targets:
        s = latest.get(t.id)
        if t.channel:
            posts_per_channel[t.channel_id] = posts_per_channel.get(t.channel_id, 0) + 1
        if not s:
            continue
        total_views += s.views
        total_likes += s.likes
        total_comments += s.comments

    # карточки каналов - все активные VK (TG пока без агрегатов, добавим с Telethon)
    channels = db.query(Channel).filter(Channel.is_active == True).all()
    channel_summaries: List[ChannelSummary] = []
    for ch in channels:
        # пока показываем только VK (для TG нужен Telethon)
        if ch.platform != Platform.vk:
            continue
        snap = db.query(ChannelSnapshot).filter(
            ChannelSnapshot.channel_id == ch.id,
        ).order_by(desc(ChannelSnapshot.captured_at)).first()
        channel_summaries.append(ChannelSummary(
            channel_id=ch.id,
            name=ch.name,
            platform=ch.platform.value,
            subscribers=snap.subscribers if snap else 0,
            avg_views=snap.avg_views if snap else 0,
            avg_likes=snap.avg_likes if snap else 0,
            posts_count=posts_per_channel.get(ch.id, 0),
        ))

    return OverviewResponse(
        total_posts=len(targets),
        total_views=total_views,
        total_likes=total_likes,
        total_comments=total_comments,
        channels=channel_summaries,
    )


@router.get("/posts", response_model=List[TopPostItem])
def top_posts(
    period_days: int = 30,
    sort_by: str = Query("views", pattern="^(views|likes|reposts|comments)$"),
    limit: int = 20,
    platform: Optional[str] = None,
    db: Session = Depends(get_db),
):
    since = datetime.now() - timedelta(days=period_days)
    q = db.query(PostTarget).filter(
        PostTarget.status == PostTargetStatus.published,
        PostTarget.published_at >= since,
    )
    targets = q.all()

    latest = _latest_stats_subquery(db)
    items: List[TopPostItem] = []

    for t in targets:
        s = latest.get(t.id)
        if not s or not t.channel:
            continue
        if platform and t.channel.platform.value != platform:
            continue
        post = t.post
        if not post:
            continue
        items.append(TopPostItem(
            post_id=post.id,
            title=post.title,
            preview=(post.text_plain or post.text_tg or "")[:120],
            platform=t.channel.platform.value,
            channel_name=t.channel.name,
            published_at=t.published_at,
            url=t.published_url,
            views=s.views,
            likes=s.likes,
            reposts=s.reposts,
            comments=s.comments,
        ))

    items.sort(key=lambda x: getattr(x, sort_by), reverse=True)
    return items[:limit]


@router.get("/subscribers", response_model=List[SubscriberSeries])
def subscriber_history(period_days: int = 30, db: Session = Depends(get_db)):
    since = datetime.now() - timedelta(days=period_days)
    channels = db.query(Channel).filter(Channel.is_active == True).all()

    series: List[SubscriberSeries] = []
    for ch in channels:
        snaps = db.query(ChannelSnapshot).filter(
            ChannelSnapshot.channel_id == ch.id,
            ChannelSnapshot.captured_at >= since,
        ).order_by(ChannelSnapshot.captured_at).all()

        # daily aggregation - last snapshot per day
        by_day: Dict[str, int] = {}
        for s in snaps:
            key = s.captured_at.strftime("%Y-%m-%d")
            by_day[key] = s.subscribers

        points = [SubscriberPoint(date=d, subscribers=v) for d, v in sorted(by_day.items())]
        series.append(SubscriberSeries(
            channel_id=ch.id,
            name=ch.name,
            platform=ch.platform.value,
            points=points,
        ))
    return series


@router.get("/best-time", response_model=List[BestTimeCell])
def best_time(period_days: int = 60, db: Session = Depends(get_db)):
    """Average views grouped by (day_of_week, hour) over period."""
    since = datetime.now() - timedelta(days=period_days)
    targets = db.query(PostTarget).filter(
        PostTarget.status == PostTargetStatus.published,
        PostTarget.published_at >= since,
    ).all()

    latest = _latest_stats_subquery(db)
    grid: Dict[tuple, list] = {}

    for t in targets:
        s = latest.get(t.id)
        if not s or not t.published_at:
            continue
        key = (t.published_at.weekday(), t.published_at.hour)
        grid.setdefault(key, []).append(s.views)

    result = []
    for (dow, hour), views_list in grid.items():
        result.append(BestTimeCell(
            day_of_week=dow,
            hour=hour,
            avg_views=sum(views_list) / len(views_list),
            posts=len(views_list),
        ))
    return result
