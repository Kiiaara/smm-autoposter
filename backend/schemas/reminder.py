from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ReminderCreate(BaseModel):
    post_id: int
    message: str
    send_at: Optional[datetime] = None  # null = после публикации


class ReminderRead(BaseModel):
    id: int
    post_id: int
    message: str
    send_at: Optional[datetime] = None
    sent: bool
    sent_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
