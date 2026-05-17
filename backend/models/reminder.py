from datetime import datetime
from sqlalchemy import Column, Integer, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from database import Base


class Reminder(Base):
    __tablename__ = "reminders"

    id = Column(Integer, primary_key=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False, index=True)
    message = Column(Text, nullable=False)
    # send_at = null означает "отправить через 2 минуты после публикации поста"
    send_at = Column(DateTime, nullable=True, index=True)
    sent = Column(Boolean, default=False)
    sent_at = Column(DateTime, nullable=True)

    post = relationship("Post", back_populates="reminders")
