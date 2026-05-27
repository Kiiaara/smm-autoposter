from datetime import datetime
from sqlalchemy import Column, String, BigInteger, DateTime, Boolean
from database import Base


class LoginRequest(Base):
    """Запрос на вход через бота. Юзер открывает t.me/<bot>?start=login_<token>,
    бот ловит /start, ставит tg_id + approved=true. Фронт поллит и логинит."""
    __tablename__ = "login_requests"

    token = Column(String, primary_key=True)  # 32-char hex, в deeplink
    tg_id = Column(BigInteger, nullable=True, index=True)  # заполняется когда юзер пишет боту
    tg_username = Column(String, nullable=True)
    tg_first_name = Column(String, nullable=True)
    approved = Column(Boolean, default=False, nullable=False)  # true когда бот подтвердил
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)  # ttl 10 мин
