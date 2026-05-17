from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models.reminder import Reminder
from schemas.reminder import ReminderCreate, ReminderRead

router = APIRouter(prefix="/api/reminders", tags=["reminders"])


@router.get("", response_model=List[ReminderRead])
def list_reminders(post_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(Reminder)
    if post_id is not None:
        q = q.filter(Reminder.post_id == post_id)
    return q.order_by(Reminder.send_at).all()


@router.post("", response_model=ReminderRead, status_code=201)
def create_reminder(data: ReminderCreate, db: Session = Depends(get_db)):
    reminder = Reminder(post_id=data.post_id, message=data.message, send_at=data.send_at)
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return reminder


@router.delete("/{reminder_id}")
def delete_reminder(reminder_id: int, db: Session = Depends(get_db)):
    r = db.get(Reminder, reminder_id)
    if not r:
        raise HTTPException(404, "Reminder not found")
    db.delete(r)
    db.commit()
    return {"ok": True}
