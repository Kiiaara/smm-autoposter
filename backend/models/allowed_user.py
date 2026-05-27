from datetime import datetime
from sqlalchemy import Column, BigInteger, String, DateTime
from database import Base


class AllowedUser(Base):
    __tablename__ = "allowed_users"

    # tg_id - primary key для старых TG-юзеров. Для email-only ставим 0 + email.
    # Чтобы оба способа жили рядом, оставляем tg_id как PK, но email сам по себе уникален.
    tg_id = Column(BigInteger, primary_key=True)
    label = Column(String, nullable=True)  # читаемое имя для удобства
    email = Column(String, nullable=True, unique=True, index=True)  # для email-входа
    added_at = Column(DateTime, default=datetime.now)
