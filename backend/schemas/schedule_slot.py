from pydantic import BaseModel, field_validator
import re


class SlotCreate(BaseModel):
    day_of_week: int  # 0=Mon, 6=Sun
    slot_time: str   # "HH:MM"

    @field_validator("day_of_week")
    @classmethod
    def validate_day(cls, v):
        if not 0 <= v <= 6:
            raise ValueError("day_of_week must be 0-6")
        return v

    @field_validator("slot_time")
    @classmethod
    def validate_time(cls, v):
        if not re.match(r"^\d{2}:\d{2}$", v):
            raise ValueError("slot_time must be HH:MM")
        h, m = int(v[:2]), int(v[3:])
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError("invalid time")
        return v


class SlotRead(BaseModel):
    id: int
    day_of_week: int
    slot_time: str

    model_config = {"from_attributes": True}


class AvailableSlot(BaseModel):
    slot_time: str
    is_free: bool
