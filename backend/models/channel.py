import enum
from sqlalchemy import Column, Integer, String, Enum, JSON, Boolean
from database import Base


class Platform(str, enum.Enum):
    tg = "tg"
    vk = "vk"
    ig = "ig"
    max = "max"
    tt = "tt"


class Channel(Base):
    __tablename__ = "channels"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    platform = Column(Enum(Platform), nullable=False, index=True)
    # TG:  {"bot_token": "...", "chat_id": "-100..."}
    # VK:  {"access_token": "...", "owner_id": "-12345", "version": "5.131"}
    # IG:  {"page_id": "...", "access_token": "..."} (stub)
    # Max: {} (stub)
    # TT:  {"username": "tpabomah_tiktok"}  (только сбор статистики, без публикации)
    config_json = Column(JSON, default=dict)
    is_active = Column(Boolean, default=True)
