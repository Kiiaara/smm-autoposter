from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Boolean
from database import Base


class EmailCode(Base):
    """Одноразовый код подтверждения email. TTL 5 минут, до 5 попыток ввода."""
    __tablename__ = "email_codes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, nullable=False, index=True)
    code_hash = Column(String, nullable=False)  # sha256 от кода, не храним сам код
    attempts = Column(Integer, default=0, nullable=False)
    used = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
