import re
import json
import httpx
from typing import Dict, Any, Optional, List
from config import settings
from publishers.base import PublishResult

# Characters that must be escaped in MarkdownV2
_MD2_ESCAPE = r'\_*[]()~`>#+-=|{}.!'


def escape_md2(text: str) -> str:
    return re.sub(r'([' + re.escape(_MD2_ESCAPE) + r'])', r'\\\1', text)


def ranges_to_md2(text: str, ranges: List[Dict]) -> str:
    """Convert raw text + (возможно пересекающиеся) format ranges to MarkdownV2.
    Используем HTML parse_mode для TG - он спокойно переносит вложенные теги.
    Но т.к. остальной код жёстко завязан на MarkdownV2, делаем токенизацию
    по позициям границ - в каждой точке открываем/закрываем нужные маркеры.
    """
    if not ranges:
        return escape_md2(text)

    MD2_MARKERS = {
        "bold": ("*", "*"),
        "italic": ("_", "_"),
        "underline": ("__", "__"),
        "strike": ("~", "~"),
        "code": ("`", "`"),
        "spoiler": ("||", "||"),
    }

    # Стратегия: для каждой позиции в тексте знаем какие форматы активны.
    # Идём по символам, открываем/закрываем маркеры на границах.
    # Для link используем особый маркер - его нельзя вкладывать в другие, поэтому
    # его открываем/закрываем последним (внутри) и пишем как [text](url).

    n = len(text)
    # Для каждой позиции - какие НЕ-link форматы активны
    active_at: List[set] = [set() for _ in range(n + 1)]
    # Для каждой позиции - какой link активен (один URL за раз)
    link_at: List[Optional[str]] = [None] * (n + 1)

    for r in ranges:
        s, e = max(0, r["start"]), min(n, r["end"])
        if e <= s:
            continue
        rtype = r["type"]
        if rtype == "link":
            for i in range(s, e):
                link_at[i] = r.get("url", "")
        elif rtype in MD2_MARKERS:
            for i in range(s, e):
                active_at[i].add(rtype)

    # Порядок открытия - стабильный, чтобы парные закрытия совпадали
    ORDER = ["bold", "italic", "underline", "strike", "spoiler", "code"]

    out: List[str] = []
    prev_active: set = set()
    prev_link: Optional[str] = None
    link_buffer: List[str] = []  # текст внутри текущей ссылки

    def flush_link():
        nonlocal prev_link
        if prev_link is not None:
            out.append("[")
            out.extend(link_buffer)
            out.append(f"]({prev_link})")
            link_buffer.clear()
            prev_link = None

    for i in range(n + 1):
        cur_active = active_at[i] if i < n else set()
        cur_link = link_at[i] if i < n else None

        # 1. Если меняется набор форматов - закрываем старые в обратном порядке,
        #    открываем новые в прямом
        if cur_active != prev_active:
            # сначала закроем link, потом форматы, потом откроем форматы и link
            flush_link()
            to_close = [t for t in reversed(ORDER) if t in prev_active and t not in cur_active]
            to_open = [t for t in ORDER if t in cur_active and t not in prev_active]
            for t in to_close:
                out.append(MD2_MARKERS[t][1])
            for t in to_open:
                out.append(MD2_MARKERS[t][0])
            prev_active = cur_active

        # 2. Link меняется - закрываем старую, открываем новую (буфер начнётся пустым)
        if cur_link != prev_link:
            flush_link()
            prev_link = cur_link

        # 3. Записываем символ если есть
        if i < n:
            ch = escape_md2(text[i])
            if prev_link is not None:
                link_buffer.append(ch)
            else:
                out.append(ch)

    # финальное закрытие
    flush_link()
    for t in reversed(ORDER):
        if t in prev_active:
            out.append(MD2_MARKERS[t][1])

    return "".join(out)


def _ranges_to_html(text: str, ranges: List[Dict]) -> str:
    """Legacy конвертер: старый формат plain + ranges → HTML для TG."""
    from html import escape as h_escape
    if not ranges:
        return h_escape(text).replace("\n", "<br>")

    n = len(text)
    active_at: List[set] = [set() for _ in range(n + 1)]
    link_at: List[Optional[str]] = [None] * (n + 1)
    TAG_MAP = {
        "bold": "b", "italic": "i", "underline": "u",
        "strike": "s", "code": "code", "spoiler": "tg-spoiler",
    }
    for r in ranges:
        s, e = max(0, r["start"]), min(n, r["end"])
        if e <= s:
            continue
        rtype = r["type"]
        if rtype == "link":
            for i in range(s, e):
                link_at[i] = r.get("url", "")
        elif rtype in TAG_MAP:
            for i in range(s, e):
                active_at[i].add(rtype)

    ORDER = ["bold", "italic", "underline", "strike", "spoiler", "code"]
    out: List[str] = []
    prev_active: set = set()
    prev_link: Optional[str] = None
    link_buf: List[str] = []

    def flush_link():
        nonlocal prev_link
        if prev_link is not None:
            url = h_escape(prev_link, quote=True)
            out.append(f'<a href="{url}">')
            out.extend(link_buf)
            out.append('</a>')
            link_buf.clear()
            prev_link = None

    for i in range(n + 1):
        cur_active = active_at[i] if i < n else set()
        cur_link = link_at[i] if i < n else None
        if cur_active != prev_active:
            flush_link()
            for t in reversed(ORDER):
                if t in prev_active and t not in cur_active:
                    out.append(f"</{TAG_MAP[t]}>")
            for t in ORDER:
                if t in cur_active and t not in prev_active:
                    out.append(f"<{TAG_MAP[t]}>")
            prev_active = cur_active
        if cur_link != prev_link:
            flush_link()
            prev_link = cur_link
        if i < n:
            ch = h_escape(text[i])
            if prev_link is not None:
                link_buf.append(ch)
            else:
                out.append(ch)
    flush_link()
    for t in reversed(ORDER):
        if t in prev_active:
            out.append(f"</{TAG_MAP[t]}>")
    return "".join(out).replace("\n", "<br>")


def _httpx_kwargs(timeout: int = 30) -> Dict:
    """Общие параметры httpx-клиента. Если в конфиге задан tg_proxy_url -
    все запросы к TG идут через прокси (SOCKS5 на РФ-сервере)."""
    kw: Dict = {"timeout": timeout}
    proxy = settings.tg_proxy_url
    if proxy:
        if proxy.startswith("socks"):
            # httpx сам по себе SOCKS не умеет - нужен httpx-socks транспорт
            from httpx_socks import AsyncProxyTransport
            kw["transport"] = AsyncProxyTransport.from_url(proxy)
        else:
            kw["proxy"] = proxy
    return kw


async def _tg_request(bot_token: str, method: str, data: Dict) -> Dict:
    url = f"https://api.telegram.org/bot{bot_token}/{method}"
    async with httpx.AsyncClient(**_httpx_kwargs(30)) as client:
        resp = await client.post(url, json=data)
    return resp.json()


def _local_path(p: str) -> str:
    """Конвертит media_path из БД в локальный путь на диске.
    В БД может быть как 'uploads/abc.jpg', так и просто 'abc.jpg'."""
    import os
    p = p.lstrip("/")
    if p.startswith("uploads/"):
        return os.path.join(settings.upload_dir, p[len("uploads/"):])
    return os.path.join(settings.upload_dir, p)


async def _tg_request_multipart(bot_token: str, method: str, data: Dict, files: Dict) -> Dict:
    """Шлёт запрос с прикреплёнными файлами через multipart/form-data.
    Используется когда TG не может скачать картинку по URL (или мы не хотим светить URL)."""
    url = f"https://api.telegram.org/bot{bot_token}/{method}"
    async with httpx.AsyncClient(**_httpx_kwargs(120)) as client:
        resp = await client.post(url, data=data, files=files)
    return resp.json()


async def publish_to_telegram(
    bot_token: str,
    chat_id: str,
    text_html: Optional[str],
    media_paths: List[str],
    poll_json: Optional[Dict],
    # legacy параметры для обратной совместимости со старыми постами
    legacy_text_raw: Optional[str] = None,
    legacy_text_ranges: Optional[List[Dict]] = None,
) -> PublishResult:
    try:
        from publishers.html_sanitize import sanitize_for_tg

        # Приоритет: HTML (новый формат). Если его нет - конвертируем старые ranges→HTML
        if text_html:
            send_text_html = sanitize_for_tg(text_html)
        elif legacy_text_raw and legacy_text_ranges:
            send_text_html = sanitize_for_tg(_ranges_to_html(legacy_text_raw, legacy_text_ranges))
        elif legacy_text_raw:
            send_text_html = sanitize_for_tg(legacy_text_raw)
        else:
            send_text_html = None

        tg_no_text = poll_json.get("tg_no_text", True) if poll_json else False
        send_text = bool(send_text_html) and not tg_no_text

        message_id = None

        if media_paths and not poll_json:
            # Грузим файлы напрямую через multipart - не зависим от TG которому надо качать наш URL.
            # Это и быстрее, и работает даже если домен где-то блокируется.
            import os, mimetypes

            if len(media_paths) == 1:
                path = _local_path(media_paths[0])
                fname = os.path.basename(path)
                mime = mimetypes.guess_type(fname)[0] or "image/jpeg"
                with open(path, "rb") as fh:
                    payload = {"chat_id": chat_id}
                    if send_text_html:
                        payload["caption"] = send_text_html
                        payload["parse_mode"] = "HTML"
                    files = {"photo": (fname, fh.read(), mime)}
                    r = await _tg_request_multipart(bot_token, "sendPhoto", payload, files)
            else:
                files = {}
                media = []
                file_handles = []
                for idx, mp in enumerate(media_paths):
                    path = _local_path(mp)
                    fname = os.path.basename(path)
                    mime = mimetypes.guess_type(fname)[0] or "image/jpeg"
                    with open(path, "rb") as fh:
                        content = fh.read()
                    attach_name = f"photo{idx}"
                    files[attach_name] = (fname, content, mime)
                    media.append({"type": "photo", "media": f"attach://{attach_name}"})
                if send_text_html:
                    media[0]["caption"] = send_text_html
                    media[0]["parse_mode"] = "HTML"
                payload = {
                    "chat_id": chat_id,
                    "media": json.dumps(media),
                }
                r = await _tg_request_multipart(bot_token, "sendMediaGroup", payload, files)
            if not r.get("ok"):
                return PublishResult(ok=False, error=r.get("description", "TG error"))
            result = r.get("result")
            if isinstance(result, list) and result:
                message_id = str(result[0].get("message_id"))
            elif isinstance(result, dict):
                message_id = str(result.get("message_id"))
        elif send_text:
            r = await _tg_request(bot_token, "sendMessage", {
                "chat_id": chat_id,
                "text": send_text_html,
                "parse_mode": "HTML",
            })
            if not r.get("ok"):
                return PublishResult(ok=False, error=r.get("description", "TG error"))
            message_id = str(r["result"].get("message_id"))

        if poll_json:
            r = await _tg_request(bot_token, "sendPoll", {
                "chat_id": chat_id,
                "question": poll_json["question"],
                "options": poll_json["options"],
                "is_anonymous": poll_json.get("is_anonymous", True),
                "allows_multiple_answers": poll_json.get("allows_multiple_answers", False),
            })
            if not r.get("ok"):
                return PublishResult(ok=False, error=r.get("description", "TG poll error"))
            if not message_id:
                message_id = str(r["result"].get("message_id"))

        # build public URL to the post
        post_url = build_post_url(bot_token, chat_id, message_id) if message_id else None

        return PublishResult(ok=True, message_id=message_id, url=post_url)
    except Exception as e:
        return PublishResult(ok=False, error=str(e))


def build_post_url(bot_token: str, chat_id: str, message_id: str) -> Optional[str]:
    """Build a t.me link to a posted message.
    For public channels with username: https://t.me/{username}/{msg_id}
    For private channels: https://t.me/c/{stripped_chat_id}/{msg_id}
    """
    # numeric chat_id - private channel link format
    if str(chat_id).lstrip('-').isdigit():
        stripped = str(chat_id).replace('-100', '').lstrip('-')
        return f"https://t.me/c/{stripped}/{message_id}"
    # @username
    if str(chat_id).startswith('@'):
        return f"https://t.me/{str(chat_id)[1:]}/{message_id}"
    return None


def normalize_chat_identifier(value: str) -> str:
    """Convert @username or t.me/username link to @username for Bot API."""
    value = value.strip()
    # https://t.me/channame or t.me/channame -> @channame
    value = re.sub(r'https?://t\.me/', '@', value)
    value = re.sub(r'^t\.me/', '@', value)
    # ensure @ prefix for usernames
    if value and not value.startswith('-') and not value.startswith('@') and not value.lstrip('-').isdigit():
        value = '@' + value
    return value


async def resolve_chat_id(bot_token: str, identifier: str) -> Optional[str]:
    """Resolve @username or link to numeric chat_id via getChat."""
    normalized = normalize_chat_identifier(identifier)
    r = await _tg_request(bot_token, "getChat", {"chat_id": normalized})
    if r.get("ok"):
        return str(r["result"]["id"])
    return None


async def test_tg_channel(config: Dict) -> Dict:
    token = config.get("bot_token", "")
    if not token:
        return {"ok": False, "message": "bot_token не указан"}

    # verify token
    async with httpx.AsyncClient(**_httpx_kwargs(10)) as client:
        r = await client.get(f"https://api.telegram.org/bot{token}/getMe")
    data = r.json()
    if not data.get("ok"):
        return {"ok": False, "message": data.get("description", "Неверный токен")}

    bot_name = data['result'].get('username')

    # if channel identifier provided - try to resolve it
    identifier = config.get("channel", "")
    if identifier:
        chat_id = await resolve_chat_id(token, identifier)
        if not chat_id:
            return {"ok": False, "message": f"Бот @{bot_name} работает, но канал '{identifier}' не найден. Убедись что бот добавлен как администратор канала."}
        return {"ok": True, "message": f"Бот @{bot_name} подключен, канал найден (id: {chat_id})", "chat_id": chat_id}

    return {"ok": True, "message": f"Бот @{bot_name} работает"}


async def send_reminder(bot_token: str, chat_id: str, text: str, parse_mode: str = "HTML") -> bool:
    payload = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    r = await _tg_request(bot_token, "sendMessage", payload)
    return r.get("ok", False)
