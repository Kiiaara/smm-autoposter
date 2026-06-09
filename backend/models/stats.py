from datetime import datetime
from sqlalchemy import Column, Integer, DateTime, ForeignKey, Index, String, Text, BigInteger, UniqueConstraint
from sqlalchemy.orm import relationship
from database import Base


class PostStats(Base):
    """Snapshot of post metrics at a specific time."""
    __tablename__ = "post_stats"

    id = Column(Integer, primary_key=True)
    post_target_id = Column(Integer, ForeignKey("post_targets.id", ondelete="CASCADE"), nullable=False, index=True)
    captured_at = Column(DateTime, nullable=False, default=datetime.now, index=True)
    views = Column(Integer, default=0)
    likes = Column(Integer, default=0)
    reposts = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    reactions = Column(Integer, default=0)

    post_target = relationship("PostTarget")


class ChannelSnapshot(Base):
    """Daily snapshot of channel-wide metrics (not just our posts)."""
    __tablename__ = "channel_snapshots"

    id = Column(Integer, primary_key=True)
    channel_id = Column(Integer, ForeignKey("channels.id", ondelete="CASCADE"), nullable=False, index=True)
    captured_at = Column(DateTime, nullable=False, default=datetime.now, index=True)
    subscribers = Column(Integer, default=0)
    # агрегаты по всем постам канала (последние ~50 постов или за период)
    avg_views = Column(Integer, default=0)
    avg_likes = Column(Integer, default=0)
    avg_reposts = Column(Integer, default=0)
    avg_comments = Column(Integer, default=0)
    posts_total = Column(Integer, default=0)  # сколько постов учтено в среднем

    channel = relationship("Channel")


class ChannelPost(Base):
    """Один пост из TG-канала со снимком метрик. Загружается локальным коллектором
    через Telethon. Один пост = одна строка (latest-снимок), обновляется при ре-сборе.
    """
    __tablename__ = "channel_posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    channel_id = Column(Integer, ForeignKey("channels.id", ondelete="CASCADE"), nullable=False, index=True)
    message_id = Column(BigInteger, nullable=False)
    text = Column(Text, default="")  # первые ~500 символов текста поста
    published_at = Column(DateTime, nullable=False, index=True)
    views = Column(Integer, default=0)
    forwards = Column(Integer, default=0)
    reactions = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    link = Column(String(512), default="")  # https://t.me/username/12345
    updated_at = Column(DateTime, nullable=False, default=datetime.now, index=True)

    channel = relationship("Channel")

    __table_args__ = (
        UniqueConstraint("channel_id", "message_id", name="uq_channel_post"),
    )


Index("ix_post_stats_target_time", PostStats.post_target_id, PostStats.captured_at)
Index("ix_channel_snap_chan_time", ChannelSnapshot.channel_id, ChannelSnapshot.captured_at)
Index("ix_channel_post_chan_pub", ChannelPost.channel_id, ChannelPost.published_at)
