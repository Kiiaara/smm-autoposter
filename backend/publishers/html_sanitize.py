"""Санитайзинг HTML для Telegram parse_mode=HTML.
Список поддерживаемых тегов: https://core.telegram.org/bots/api#html-style

Скопировано из streamer-bot/shared/html_sanitize.py - проверенная реализация.
"""
import re
import bleach

ALLOWED_TAGS = [
    "b", "strong",
    "i", "em",
    "u", "ins",
    "s", "strike", "del",
    "code", "pre",
    "a",
    "tg-spoiler",
]

ALLOWED_ATTRS = {
    "a": ["href"],
}


def sanitize_for_tg(html: str) -> str:
    """Очищает HTML до Telegram-совместимого подмножества тегов.
    <br>, <p>, <div> → \\n (TG не понимает их, но \\n даёт визуально то же)."""
    if not html:
        return ""
    s = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    s = re.sub(r"</(p|div)>", "\n", s, flags=re.IGNORECASE)
    s = re.sub(r"<(p|div)[^>]*>", "", s, flags=re.IGNORECASE)
    s = s.replace("&nbsp;", " ").replace("&#160;", " ")

    cleaned = bleach.clean(
        s,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRS,
        strip=True,
        strip_comments=True,
    )
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def html_to_plain(html: str) -> str:
    """HTML → plain text (для VK/IG/Max и для превью без форматирования)."""
    if not html:
        return ""
    s = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    s = re.sub(r"</(p|div)>", "\n", s, flags=re.IGNORECASE)
    # ссылки <a href="X">текст</a> → "текст (X)"
    def repl_link(m):
        href = m.group(1)
        text = re.sub(r"<[^>]+>", "", m.group(2))
        if href and href != text:
            return f"{text} ({href})"
        return text
    s = re.sub(r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', repl_link, s, flags=re.IGNORECASE | re.DOTALL)
    # убираем все остальные теги
    s = re.sub(r"<[^>]+>", "", s)
    s = s.replace("&nbsp;", " ").replace("&#160;", " ")
    s = s.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()
