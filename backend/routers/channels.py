from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models.channel import Channel, Platform
from schemas.channel import ChannelCreate, ChannelUpdate, ChannelRead

router = APIRouter(prefix="/api/channels", tags=["channels"])


def _safe_read(ch: Channel) -> ChannelRead:
    # strip sensitive keys from config_json before returning
    safe = {k: ("***" if k in ("bot_token", "access_token") else v)
            for k, v in (ch.config_json or {}).items()}
    return ChannelRead(
        id=ch.id,
        name=ch.name,
        platform=ch.platform,
        is_active=ch.is_active,
        config_json=safe,
    )


@router.get("", response_model=List[ChannelRead])
def list_channels(platform: Optional[Platform] = None, db: Session = Depends(get_db)):
    q = db.query(Channel)
    if platform:
        q = q.filter(Channel.platform == platform)
    return [_safe_read(ch) for ch in q.all()]


@router.post("", response_model=ChannelRead, status_code=201)
async def create_channel(data: ChannelCreate, db: Session = Depends(get_db)):
    config = dict(data.config_json)

    # for TG: auto-resolve channel username/link to numeric chat_id
    if data.platform.value == "tg":
        from publishers.telegram import resolve_chat_id, normalize_chat_identifier
        token = config.get("bot_token", "")
        identifier = config.get("channel", "")
        if token and identifier:
            chat_id = await resolve_chat_id(token, identifier)
            if not chat_id:
                raise HTTPException(400, f"Канал '{identifier}' не найден. Убедись что бот добавлен как администратор канала.")
            config["chat_id"] = chat_id

    ch = Channel(name=data.name, platform=data.platform, config_json=config)
    db.add(ch)
    db.commit()
    db.refresh(ch)
    return _safe_read(ch)


@router.get("/{ch_id}", response_model=ChannelRead)
def get_channel(ch_id: int, db: Session = Depends(get_db)):
    ch = db.get(Channel, ch_id)
    if not ch:
        raise HTTPException(404, "Channel not found")
    return _safe_read(ch)


@router.patch("/{ch_id}", response_model=ChannelRead)
async def update_channel(ch_id: int, data: ChannelUpdate, db: Session = Depends(get_db)):
    ch = db.get(Channel, ch_id)
    if not ch:
        raise HTTPException(404, "Channel not found")

    payload = data.model_dump(exclude_unset=True)

    # config_json приходит частичный - сливаем со старым, пустые токены не перезаписываем
    if "config_json" in payload and payload["config_json"] is not None:
        merged = dict(ch.config_json or {})
        for k, v in payload["config_json"].items():
            # пустая строка токена = "не менять"
            if k in ("bot_token", "access_token") and not v:
                continue
            merged[k] = v
        payload["config_json"] = merged

        # для TG если канал/токен поменялись - перерезолвить chat_id
        if ch.platform.value == "tg":
            from publishers.telegram import resolve_chat_id
            token = merged.get("bot_token", "")
            identifier = merged.get("channel", "")
            if token and identifier:
                chat_id = await resolve_chat_id(token, identifier)
                if not chat_id:
                    raise HTTPException(400, f"Канал '{identifier}' не найден. Бот должен быть админом канала.")
                merged["chat_id"] = chat_id
                payload["config_json"] = merged

    for field, value in payload.items():
        setattr(ch, field, value)
    db.commit()
    db.refresh(ch)
    return _safe_read(ch)


@router.delete("/{ch_id}")
def delete_channel(ch_id: int, db: Session = Depends(get_db)):
    ch = db.get(Channel, ch_id)
    if not ch:
        raise HTTPException(404, "Channel not found")
    db.delete(ch)
    db.commit()
    return {"ok": True}


@router.post("/{ch_id}/test")
async def test_channel(ch_id: int, db: Session = Depends(get_db)):
    from publishers.telegram import test_tg_channel
    from publishers.vk import test_vk_channel
    ch = db.get(Channel, ch_id)
    if not ch:
        raise HTTPException(404, "Channel not found")
    if ch.platform.value == "tg":
        return await test_tg_channel(ch.config_json)
    elif ch.platform.value == "vk":
        return await test_vk_channel(ch.config_json)
    return {"ok": True, "message": f"{ch.platform.value} stub - no test available"}
