from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel
from models.post import PostStatus, PostTargetStatus


class FormatRange(BaseModel):
    start: int
    end: int
    type: str  # bold, italic, strike, code, spoiler, link
    url: Optional[str] = None  # only for type="link"


class PollData(BaseModel):
    question: str
    options: List[str]
    is_anonymous: bool = True
    allows_multiple_answers: bool = False
    tg_no_text: bool = True  # publish poll without text in TG


class PostTargetCreate(BaseModel):
    channel_id: int


class PostTargetRead(BaseModel):
    id: int
    channel_id: int
    status: PostTargetStatus
    published_at: Optional[datetime] = None
    error: Optional[str] = None

    model_config = {"from_attributes": True}


class PostCreate(BaseModel):
    title: Optional[str] = None
    text_tg_html: Optional[str] = None  # новый формат - HTML
    text_tg: Optional[str] = None  # legacy
    text_tg_ranges: List[FormatRange] = []  # legacy
    text_plain: Optional[str] = None
    media_paths: List[str] = []
    poll_json: Optional[PollData] = None
    status: PostStatus = PostStatus.draft
    scheduled_at: Optional[datetime] = None
    targets: List[PostTargetCreate] = []


class PostUpdate(BaseModel):
    title: Optional[str] = None
    text_tg_html: Optional[str] = None
    text_tg: Optional[str] = None
    text_tg_ranges: Optional[List[FormatRange]] = None
    text_plain: Optional[str] = None
    media_paths: Optional[List[str]] = None
    poll_json: Optional[PollData] = None
    status: Optional[PostStatus] = None
    scheduled_at: Optional[datetime] = None
    targets: Optional[List[PostTargetCreate]] = None


class PostRead(BaseModel):
    id: int
    title: Optional[str]
    text_tg_html: Optional[str] = None
    text_tg: Optional[str]
    text_tg_ranges: List[Any]
    text_plain: Optional[str]
    media_paths: List[str]
    poll_json: Optional[Any]
    status: PostStatus
    scheduled_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    targets: List[PostTargetRead]

    model_config = {"from_attributes": True}


class PostListItem(BaseModel):
    id: int
    title: Optional[str]
    status: PostStatus
    scheduled_at: Optional[datetime]
    created_at: datetime
    platforms: List[str] = []
    preview_text: Optional[str] = None

    model_config = {"from_attributes": True}
