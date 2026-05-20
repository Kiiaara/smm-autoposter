from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db
from models.post import Post, PostStatus
from models.schedule_slot import ScheduleSlot

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


def _post_preview(p) -> str:
    """Берёт превью текста поста - предпочитая HTML, потом legacy text_tg, потом plain."""
    if p.text_tg_html:
        from publishers.html_sanitize import html_to_plain
        return html_to_plain(p.text_tg_html)
    return p.text_tg or p.text_plain or ""


class TargetStatus(BaseModel):
    channel_name: str
    platform: str
    status: str
    error: Optional[str] = None
    url: Optional[str] = None


class CalendarPost(BaseModel):
    id: int
    title: Optional[str]
    status: str
    scheduled_at: datetime
    platforms: List[str]
    preview_text: Optional[str]
    has_poll: bool
    targets: List[TargetStatus] = []


class CalendarSlot(BaseModel):
    slot_time: str
    is_free: bool


class CalendarDay(BaseModel):
    date: str
    slots: List[CalendarSlot]
    posts: List[CalendarPost]


class CalendarResponse(BaseModel):
    week_start: str
    days: List[CalendarDay]


@router.get("", response_model=CalendarResponse)
def get_calendar(week_start: str, db: Session = Depends(get_db)):
    try:
        ws = datetime.strptime(week_start, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(400, "week_start must be YYYY-MM-DD")

    we = ws + timedelta(days=7)

    posts = db.query(Post).filter(
        Post.scheduled_at >= ws,
        Post.scheduled_at < we,
    ).order_by(Post.scheduled_at).all()

    # group posts by date
    posts_by_date: Dict[str, List[Post]] = {}
    for p in posts:
        key = p.scheduled_at.strftime("%Y-%m-%d")
        posts_by_date.setdefault(key, []).append(p)

    days = []
    for i in range(7):
        day = ws + timedelta(days=i)
        day_str = day.strftime("%Y-%m-%d")
        dow = day.weekday()

        slots_db = db.query(ScheduleSlot).filter(ScheduleSlot.day_of_week == dow)\
                     .order_by(ScheduleSlot.slot_time).all()

        day_posts = posts_by_date.get(day_str, [])
        busy_times = {p.scheduled_at.strftime("%H:%M") for p in day_posts if p.scheduled_at}

        calendar_slots = [CalendarSlot(slot_time=s.slot_time, is_free=s.slot_time not in busy_times)
                          for s in slots_db]

        calendar_posts = []
        for p in day_posts:
            platforms = list({t.channel.platform.value for t in p.targets if t.channel})
            target_statuses = [
                TargetStatus(
                    channel_name=t.channel.name if t.channel else "?",
                    platform=t.channel.platform.value if t.channel else "?",
                    status=t.status.value,
                    error=t.error,
                    url=t.published_url,
                )
                for t in p.targets
            ]
            calendar_posts.append(CalendarPost(
                id=p.id,
                title=p.title,
                status=p.status.value,
                scheduled_at=p.scheduled_at,
                platforms=platforms,
                preview_text=_post_preview(p)[:100],
                has_poll=p.poll_json is not None,
                targets=target_statuses,
            ))

        days.append(CalendarDay(date=day_str, slots=calendar_slots, posts=calendar_posts))

    return CalendarResponse(week_start=week_start, days=days)
