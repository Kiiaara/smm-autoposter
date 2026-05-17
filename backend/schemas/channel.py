from typing import Optional, Dict, Any
from pydantic import BaseModel
from models.channel import Platform


class ChannelCreate(BaseModel):
    name: str
    platform: Platform
    config_json: Dict[str, Any] = {}


class ChannelUpdate(BaseModel):
    name: Optional[str] = None
    config_json: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class ChannelRead(BaseModel):
    id: int
    name: str
    platform: Platform
    is_active: bool
    # config_json returned without sensitive tokens
    config_json: Dict[str, Any] = {}

    model_config = {"from_attributes": True}
