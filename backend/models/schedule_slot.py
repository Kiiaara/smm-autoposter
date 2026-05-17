from sqlalchemy import Column, Integer, String, UniqueConstraint
from database import Base


class ScheduleSlot(Base):
    __tablename__ = "schedule_slots"

    id = Column(Integer, primary_key=True)
    # 0 = Monday ... 6 = Sunday (Python weekday convention)
    day_of_week = Column(Integer, nullable=False)
    slot_time = Column(String(5), nullable=False)  # "HH:MM"

    __table_args__ = (UniqueConstraint("day_of_week", "slot_time"),)
