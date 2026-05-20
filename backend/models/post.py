import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Enum, JSON, ForeignKey
from sqlalchemy.orm import relationship
from database import Base


class PostStatus(str, enum.Enum):
    draft = "draft"
    scheduled = "scheduled"
    published = "published"
    failed = "failed"


class PostTargetStatus(str, enum.Enum):
    pending = "pending"
    published = "published"
    failed = "failed"


class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=True)
    # для TG: HTML с форматированием (новый формат, parse_mode=HTML)
    text_tg_html = Column(Text, nullable=True)
    # legacy: plain text + ranges (для старых постов, постепенно мигрируем)
    text_tg = Column(Text, nullable=True)
    text_tg_ranges = Column(JSON, default=list)
    # plain text for VK / Instagram / Max
    text_plain = Column(Text, nullable=True)
    media_paths = Column(JSON, default=list)
    # poll data: {"question": str, "options": [...], "is_anonymous": bool,
    #             "allows_multiple_answers": bool, "tg_no_text": bool}
    poll_json = Column(JSON, nullable=True)
    status = Column(Enum(PostStatus), default=PostStatus.draft, index=True)
    scheduled_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    targets = relationship("PostTarget", back_populates="post", cascade="all, delete-orphan")
    reminders = relationship("Reminder", back_populates="post", cascade="all, delete-orphan")


class PostTarget(Base):
    __tablename__ = "post_targets"

    id = Column(Integer, primary_key=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False, index=True)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False)
    status = Column(Enum(PostTargetStatus), default=PostTargetStatus.pending)
    published_at = Column(DateTime, nullable=True)
    published_message_id = Column(String(50), nullable=True)
    published_url = Column(String(500), nullable=True)
    error = Column(Text, nullable=True)

    post = relationship("Post", back_populates="targets")
    channel = relationship("Channel")
