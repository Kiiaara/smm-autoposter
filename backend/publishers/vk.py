import json
import httpx
from typing import Dict, Optional, List
from publishers.base import PublishResult

VK_API = "https://api.vk.com/method"


async def _vk(method: str, params: Dict, token: str, version: str = "5.131") -> Dict:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{VK_API}/{method}", params={
            **params,
            "access_token": token,
            "v": version,
        })
    return r.json()


async def _upload_photo(token: str, owner_id: str, path: str, version: str) -> Optional[str]:
    """Upload a local file to VK wall. Returns attachment string like 'photo123_456'."""
    # photos.getWallUploadServer для групп требует group_id (положительный, без минуса)
    is_group = str(owner_id).startswith("-")
    group_id = str(owner_id).lstrip("-")

    server_params = {"group_id": group_id} if is_group else {}
    r = await _vk("photos.getWallUploadServer", server_params, token, version)
    if "error" in r:
        return None
    upload_url = r["response"]["upload_url"]

    # step 2: upload file
    with open(path.replace("uploads/", "./uploads/"), "rb") as f:
        content = f.read()
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(upload_url, files={"photo": ("photo.jpg", content, "image/jpeg")})
    upload_data = resp.json()

    # step 3: save photo - аналогично, для группы передаём group_id
    save_params = {
        "server": upload_data.get("server"),
        "photo": upload_data.get("photo"),
        "hash": upload_data.get("hash"),
    }
    if is_group:
        save_params["group_id"] = group_id
    r2 = await _vk("photos.saveWallPhoto", save_params, token, version)
    if "error" in r2 or not r2.get("response"):
        return None

    photo = r2["response"][0]
    return f"photo{photo['owner_id']}_{photo['id']}"


async def publish_to_vk(
    access_token: str,
    owner_id: str,
    text_plain: Optional[str],
    media_paths: List[str],
    poll_json: Optional[Dict],
    version: str = "5.131",
) -> PublishResult:
    try:
        attachments = []

        # upload photos
        for path in media_paths:
            att = await _upload_photo(access_token, owner_id, path, version)
            if att:
                attachments.append(att)

        # create poll if present
        if poll_json:
            poll_params = {
                "owner_id": owner_id,
                "question": poll_json["question"],
                "add_answers": json.dumps(poll_json["options"], ensure_ascii=False),
                "is_anonymous": 1 if poll_json.get("is_anonymous", True) else 0,
                "disable_unvote": 0,
            }
            r = await _vk("polls.create", poll_params, access_token, version)
            if "response" in r:
                poll_id = r["response"]["id"]
                poll_owner = r["response"].get("owner_id", owner_id)
                attachments.append(f"poll{poll_owner}_{poll_id}")
            else:
                err_msg = r.get("error", {}).get("error_msg", "polls.create failed")
                return PublishResult(ok=False, error=f"Опрос не создан: {err_msg}")

        # VK не принимает пост только с poll без message/photo/video/link.
        # Валидация описания должна быть на фронте, тут просто публикуем что есть.
        wall_params = {"owner_id": owner_id}
        if text_plain and text_plain.strip():
            wall_params["message"] = text_plain
        if attachments:
            wall_params["attachments"] = ",".join(attachments)
        # пробуем как user-токен (with from_group), если ругается на group auth - ретрай без него
        if str(owner_id).startswith("-"):
            wall_params["from_group"] = 1
        r = await _vk("wall.post", wall_params, access_token, version)
        if "error" in r and "Group authorization" in r["error"].get("error_msg", ""):
            wall_params.pop("from_group", None)
            r = await _vk("wall.post", wall_params, access_token, version)

        if "error" in r:
            return PublishResult(ok=False, error=r["error"].get("error_msg", "VK error"))
        post_id = str(r["response"]["post_id"])
        # VK post URL: https://vk.com/wall{owner_id}_{post_id}
        post_url = f"https://vk.com/wall{owner_id}_{post_id}"
        return PublishResult(ok=True, message_id=post_id, url=post_url)
    except Exception as e:
        return PublishResult(ok=False, error=str(e))


async def test_vk_channel(config: Dict) -> Dict:
    token = config.get("access_token", "")
    owner_id = config.get("owner_id", "")
    if not token:
        return {"ok": False, "message": "access_token не указан"}

    # пробуем универсальный метод - получить инфо о группе
    # group-токен вернёт свою группу, user-токен - запрошенную
    group_id = str(owner_id).lstrip("-") if owner_id else ""
    params = {"group_id": group_id} if group_id else {}
    r = await _vk("groups.getById", params, token)

    if "response" in r:
        groups = r["response"].get("groups") if isinstance(r["response"], dict) else r["response"]
        if groups and len(groups) > 0:
            name = groups[0].get("name", "?")
            return {"ok": True, "message": f"Токен валиден, группа: {name}"}
        return {"ok": True, "message": "Токен валиден"}

    return {"ok": False, "message": r.get("error", {}).get("error_msg", "Невалидный токен")}
