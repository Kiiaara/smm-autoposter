from datetime import datetime
from sqlalchemy import Column, String, BigInteger, DateTime
from database import Base


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    token = Column(String, primary_key=True)  # случайный 64-char hex
    tg_id = Column(BigInteger, nullable=False, index=True)
    tg_username = Column(String, nullable=True)
    tg_first_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    expires_at = Column(DateTime, nullable=False, index=True)
