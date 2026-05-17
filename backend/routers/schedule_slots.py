from datetime import datetime, date, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models.schedule_slot import ScheduleSlot
from models.post import Post, PostStatus
from schemas.schedule_slot import SlotCreate, SlotRead, AvailableSlot
from sqlalchemy.exc import IntegrityError

router = APIRouter(prefix="/api/schedule-slots", tags=["schedule-slots"])


@router.get("", response_model=List[SlotRead])
def list_slots(day_of_week: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(ScheduleSlot)
    if day_of_week is not None:
        q = q.filter(ScheduleSlot.day_of_week == day_of_week)
    return q.order_by(ScheduleSlot.day_of_week, ScheduleSlot.slot_time).all()


@router.post("", response_model=SlotRead, status_code=201)
def create_slot(data: SlotCreate, db: Session = Depends(get_db)):
    slot = ScheduleSlot(day_of_week=data.day_of_week, slot_time=data.slot_time)
    db.add(slot)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Slot already exists")
    db.refresh(slot)
    return slot


@router.delete("/{slot_id}")
def delete_slot(slot_id: int, db: Session = Depends(get_db)):
    slot = db.get(ScheduleSlot, slot_id)
    if not slot:
        raise HTTPException(404, "Slot not found")
    db.delete(slot)
    db.commit()
    return {"ok": True}


@router.get("/available", response_model=List[AvailableSlot])
def available_slots(date_str: str, db: Session = Depends(get_db)):
    """Returns schedule slots for a given date with is_free flag."""
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(400, "date must be YYYY-MM-DD")

    dow = d.weekday()  # 0=Mon, 6=Sun
    slots = db.query(ScheduleSlot).filter(ScheduleSlot.day_of_week == dow)\
              .order_by(ScheduleSlot.slot_time).all()

    # find scheduled posts on this date
    day_start = datetime(d.year, d.month, d.day)
    day_end = day_start + timedelta(days=1)
    busy_times = set()
    posts = db.query(Post).filter(
        Post.status == PostStatus.scheduled,
        Post.scheduled_at >= day_start,
        Post.scheduled_at < day_end,
    ).all()
    for p in posts:
        if p.scheduled_at:
            busy_times.add(p.scheduled_at.strftime("%H:%M"))

    return [AvailableSlot(slot_time=s.slot_time, is_free=s.slot_time not in busy_times) for s in slots]
