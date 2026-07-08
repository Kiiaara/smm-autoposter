import io
import re
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from pydantic import BaseModel

from config import settings
from database import get_db
from models.post import Post, PostTarget, PostTargetStatus
from models.channel import Channel, Platform
from models.stats import PostStats, ChannelSnapshot, ChannelPost

router = APIRouter(prefix="/api/stats", tags=["stats"])


class TopPostItem(BaseModel):
    post_id: int
    title: Optional[str]
    preview: Optional[str]
    platform: str
    channel_name: str
    published_at: datetime
    url: Optional[str]
    views: int
    likes: int
    reposts: int
    comments: int


class ChannelSummary(BaseModel):
    """Полный срез по каналу (не зависит от того что мы публиковали)."""
    channel_id: int
    name: str
    platform: str
    subscribers: int
    posts_count: int  # всего постов в канале (по выборке из VK API)
    avg_views: int
    avg_likes: int


class ServicePostsSummary(BaseModel):
    """Срез только по постам опубликованным через наш сервис за период."""
    channel_id: int
    name: str
    platform: str
    posts_count: int
    avg_views: int
    avg_likes: int
    avg_comments: int
    avg_reposts: int = 0
    total_views: int
    total_likes: int
    total_reposts: int = 0
    total_comments: int = 0


class SubscriberPoint(BaseModel):
    date: str
    subscribers: int


class SubscriberSeries(BaseModel):
    channel_id: int
    name: str
    platform: str
    points: List[SubscriberPoint]


class BestTimeCell(BaseModel):
    day_of_week: int  # 0=Mon, 6=Sun
    hour: int
    avg_views: float
    posts: int


class OverviewResponse(BaseModel):
    total_posts: int
    total_views: int
    total_likes: int
    total_comments: int
    channels: List[ChannelSummary]
    service_posts: List[ServicePostsSummary] = []


def _latest_stats_subquery(db: Session):
    """Return mapping post_target_id -> latest PostStats."""
    latest = db.query(
        PostStats.post_target_id,
        func.max(PostStats.captured_at).label("max_t"),
    ).group_by(PostStats.post_target_id).subquery()

    rows = db.query(PostStats).join(
        latest,
        (PostStats.post_target_id == latest.c.post_target_id) &
        (PostStats.captured_at == latest.c.max_t),
    ).all()
    return {r.post_target_id: r for r in rows}


@router.get("/overview", response_model=OverviewResponse)
async def overview(period_days: int = 30, db: Session = Depends(get_db)):
    since = datetime.now() - timedelta(days=period_days)

    # наши посты за период
    targets = db.query(PostTarget).filter(
        PostTarget.status == PostTargetStatus.published,
        PostTarget.published_at >= since,
    ).all()
    latest = _latest_stats_subquery(db)

    # TG: метрики наших TG-таргетов берём из channel_posts (Telethon-сборщик),
    # а не из TGStat. Один запрос на все каналы - индекс по (channel_id, message_id).
    tg_posts_cache: Dict[int, Dict[int, ChannelPost]] = {}  # channel_id -> {msg_id: ChannelPost}
    tg_target_ids: set = set()
    from models.channel import Platform as _Plat
    tg_targets = [t for t in targets if t.channel and t.channel.platform == _Plat.tg and t.published_message_id]
    if tg_targets:
        ch_ids = {t.channel_id for t in tg_targets}
        cps = db.query(ChannelPost).filter(
            ChannelPost.channel_id.in_(ch_ids),
            ChannelPost.published_at >= since,
        ).all()
        for cp in cps:
            tg_posts_cache.setdefault(cp.channel_id, {})[int(cp.message_id)] = cp

    def _tg_metrics_for_target(t: PostTarget):
        """(views, likes, reposts, comments) для TG-таргета из channel_posts."""
        if not t.channel or t.channel.platform.value != "tg":
            return None
        cache = tg_posts_cache.get(t.channel_id) or {}
        try:
            msg_id = int(t.published_message_id) if t.published_message_id else None
        except (ValueError, TypeError):
            return None
        if not msg_id:
            return None
        cp = cache.get(msg_id)
        if not cp:
            return None
        return int(cp.views or 0), int(cp.reactions or 0), int(cp.forwards or 0), int(cp.comments or 0)

    # тоталы + агрегация по каналу для service_posts
    total_views = total_likes = total_comments = 0
    service_agg: Dict[int, dict] = {}
    for t in targets:
        if t.channel:
            agg = service_agg.setdefault(t.channel_id, {
                "channel": t.channel, "views": 0, "likes": 0, "comments": 0, "reposts": 0, "count": 0,
            })
            agg["count"] += 1
            tg_targ_id = id(t)
            # TG: метрики из TGStat
            tg_m = _tg_metrics_for_target(t)
            if tg_m:
                views, likes, reposts, comments = tg_m
                total_views += views
                total_likes += likes
                total_comments += comments
                agg["views"] += views
                agg["likes"] += likes
                agg["comments"] += comments
                agg["reposts"] += reposts
                tg_target_ids.add(tg_targ_id)
                continue
        # VK / прочее: из БД
        s = latest.get(t.id)
        if not s:
            continue
        total_views += s.views
        total_likes += s.likes
        total_comments += s.comments
        if t.channel:
            agg["views"] += s.views
            agg["likes"] += s.likes
            agg["comments"] += s.comments
            agg["reposts"] += s.reposts

    # Сравнение каналов - все активные (VK + TG если настроен Telethon)
    channels = db.query(Channel).filter(Channel.is_active == True).all()
    channel_summaries: List[ChannelSummary] = []
    for ch in channels:
        snap = db.query(ChannelSnapshot).filter(
            ChannelSnapshot.channel_id == ch.id,
        ).order_by(desc(ChannelSnapshot.captured_at)).first()
        # пропускаем каналы без снапшотов с метриками (например IG/MAX)
        if not snap:
            continue
        channel_summaries.append(ChannelSummary(
            channel_id=ch.id,
            name=ch.name,
            platform=ch.platform.value,
            subscribers=snap.subscribers or 0,
            posts_count=snap.posts_total or 0,
            avg_views=snap.avg_views or 0,
            avg_likes=snap.avg_likes or 0,
        ))

    # Срез по нашим постам
    service_posts: List[ServicePostsSummary] = []
    for ch_id, agg in service_agg.items():
        ch = agg["channel"]
        count = agg["count"] or 1
        service_posts.append(ServicePostsSummary(
            channel_id=ch_id,
            name=ch.name,
            platform=ch.platform.value,
            posts_count=agg["count"],
            avg_views=agg["views"] // count,
            avg_likes=agg["likes"] // count,
            avg_comments=agg["comments"] // count,
            avg_reposts=agg["reposts"] // count,
            total_views=agg["views"],
            total_likes=agg["likes"],
            total_reposts=agg["reposts"],
            total_comments=agg["comments"],
        ))

    return OverviewResponse(
        total_posts=len(targets),
        total_views=total_views,
        total_likes=total_likes,
        total_comments=total_comments,
        channels=channel_summaries,
        service_posts=service_posts,
    )


@router.get("/posts", response_model=List[TopPostItem])
async def top_posts(
    period_days: int = 30,
    sort_by: str = Query("views", pattern="^(views|likes|reposts|comments)$"),
    limit: int = 20,
    platform: Optional[str] = None,
    channel_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Топ постов за период.

    Источники:
    - VK: PostTarget'ы опубликованные через сервис (с PostStats из VK API).
    - TG: посты канала тянем напрямую из TGStat - не только наши, а ВСЕ посты
      канала. Так удобнее смотреть кто реально стрельнул.
    """
    since = datetime.now() - timedelta(days=period_days)
    items: List[TopPostItem] = []

    want_vk = platform in (None, "vk")
    want_tg = platform in (None, "tg")
    want_tt = platform in (None, "tt")

    # VK: из БД, как и раньше
    if want_vk:
        q = db.query(PostTarget).filter(
            PostTarget.status == PostTargetStatus.published,
            PostTarget.published_at >= since,
        )
        targets = q.all()
        latest = _latest_stats_subquery(db)
        for t in targets:
            if not t.channel or t.channel.platform != Platform.vk:
                continue
            if channel_id and t.channel_id != channel_id:
                continue
            s = latest.get(t.id)
            if not s:
                continue
            post = t.post
            if not post:
                continue
            items.append(TopPostItem(
                post_id=post.id,
                title=post.title,
                preview=(post.text_plain or post.text_tg or "")[:120],
                platform="vk",
                channel_name=t.channel.name,
                published_at=t.published_at,
                url=t.published_url,
                views=s.views,
                likes=s.likes,
                reposts=s.reposts,
                comments=s.comments,
            ))

    # TG: посты канала из ChannelPost (заливает локальный коллектор через Telethon)
    if want_tg:
        tg_q = db.query(ChannelPost).join(Channel).filter(
            Channel.platform == Platform.tg,
            ChannelPost.published_at >= since,
        )
        if channel_id:
            tg_q = tg_q.filter(ChannelPost.channel_id == channel_id)
        for cp in tg_q.all():
            ch = cp.channel
            if not ch:
                continue
            items.append(TopPostItem(
                post_id=int(cp.message_id),
                title=None,
                preview=(cp.text or "")[:160],
                platform="tg",
                channel_name=ch.name,
                published_at=cp.published_at,
                url=cp.link or None,
                views=cp.views or 0,
                likes=cp.reactions or 0,
                reposts=cp.forwards or 0,
                comments=cp.comments or 0,
            ))

    # TT: посты канала из ChannelPost (заливает tt_collector через TikTokApi)
    if want_tt:
        tt_q = db.query(ChannelPost).join(Channel).filter(
            Channel.platform == Platform.tt,
            ChannelPost.published_at >= since,
        )
        if channel_id:
            tt_q = tt_q.filter(ChannelPost.channel_id == channel_id)
        for cp in tt_q.all():
            ch = cp.channel
            if not ch:
                continue
            items.append(TopPostItem(
                post_id=int(cp.message_id),
                title=None,
                preview=(cp.text or "")[:160],
                platform="tt",
                channel_name=ch.name,
                published_at=cp.published_at,
                url=cp.link or None,
                views=cp.views or 0,
                likes=cp.reactions or 0,
                reposts=cp.forwards or 0,
                comments=cp.comments or 0,
            ))

    items.sort(key=lambda x: getattr(x, sort_by), reverse=True)
    return items[:limit]


@router.get("/subscribers", response_model=List[SubscriberSeries])
def subscriber_history(period_days: int = 30, db: Session = Depends(get_db)):
    since = datetime.now() - timedelta(days=period_days)
    channels = db.query(Channel).filter(Channel.is_active == True).all()

    series: List[SubscriberSeries] = []
    for ch in channels:
        snaps = db.query(ChannelSnapshot).filter(
            ChannelSnapshot.channel_id == ch.id,
            ChannelSnapshot.captured_at >= since,
        ).order_by(ChannelSnapshot.captured_at).all()

        # daily aggregation - last snapshot per day
        by_day: Dict[str, int] = {}
        for s in snaps:
            key = s.captured_at.strftime("%Y-%m-%d")
            by_day[key] = s.subscribers

        points = [SubscriberPoint(date=d, subscribers=v) for d, v in sorted(by_day.items())]
        series.append(SubscriberSeries(
            channel_id=ch.id,
            name=ch.name,
            platform=ch.platform.value,
            points=points,
        ))
    return series


@router.get("/best-time", response_model=List[BestTimeCell])
def best_time(period_days: int = 60, db: Session = Depends(get_db)):
    """Average views grouped by (day_of_week, hour) over period."""
    since = datetime.now() - timedelta(days=period_days)
    targets = db.query(PostTarget).filter(
        PostTarget.status == PostTargetStatus.published,
        PostTarget.published_at >= since,
    ).all()

    latest = _latest_stats_subquery(db)
    grid: Dict[tuple, list] = {}

    for t in targets:
        s = latest.get(t.id)
        if not s or not t.published_at:
            continue
        key = (t.published_at.weekday(), t.published_at.hour)
        grid.setdefault(key, []).append(s.views)

    result = []
    for (dow, hour), views_list in grid.items():
        result.append(BestTimeCell(
            day_of_week=dow,
            hour=hour,
            avg_views=sum(views_list) / len(views_list),
            posts=len(views_list),
        ))
    return result


def _strip_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s or "")
    return s.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").strip()


@router.get("/posts/export.xlsx")
async def export_posts_xlsx(
    channel_id: int,
    period_days: int = 30,
    db: Session = Depends(get_db),
):
    """Экспорт всех постов канала за период в XLSX (для TG-каналов через TGStat).
    Для VK - наши опубликованные через сервис посты + PostStats."""
    ch = db.get(Channel, channel_id)
    if not ch:
        raise HTTPException(404, "Channel not found")
    since = datetime.now() - timedelta(days=period_days)

    rows: List[dict] = []  # {date, text, views, forwards, reactions, comments, link}

    if ch.platform == Platform.tg:
        # TG-посты теперь лежат в channel_posts (наполняется Telethon-сборщиком).
        # Берём оттуда всё за период, сортируем по дате.
        posts = db.query(ChannelPost).filter(
            ChannelPost.channel_id == channel_id,
            ChannelPost.published_at >= since,
        ).order_by(ChannelPost.published_at.desc()).all()

        for p in posts:
            rows.append({
                "date": p.published_at.strftime("%Y-%m-%d %H:%M"),
                "text": _strip_html(p.text or ""),
                "views": int(p.views or 0),
                "forwards": int(p.forwards or 0),
                "reactions": int(p.reactions or 0),
                "comments": int(p.comments or 0),
                "link": p.link or "",
            })

    elif ch.platform == Platform.vk:
        targets = db.query(PostTarget).filter(
            PostTarget.status == PostTargetStatus.published,
            PostTarget.published_at >= since,
            PostTarget.channel_id == channel_id,
        ).all()
        latest = _latest_stats_subquery(db)
        for t in targets:
            s = latest.get(t.id)
            if not s or not t.published_at:
                continue
            text = (t.post.text_plain or t.post.text_tg or "") if t.post else ""
            rows.append({
                "date": t.published_at.strftime("%Y-%m-%d %H:%M"),
                "text": text,
                "views": s.views,
                "forwards": s.reposts,
                "reactions": s.likes,
                "comments": s.comments,
                "link": t.published_url or "",
            })
    else:
        raise HTTPException(400, "Экспорт пока поддерживается только для TG и VK")

    rows.sort(key=lambda r: r["date"], reverse=True)

    # формируем XLSX
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill
    wb = Workbook()
    ws = wb.active
    ws.title = ch.name[:30]
    headers = ["Дата", "Текст", "Просмотры", "Пересылки", "Реакции", "Комментарии", "Ссылка"]
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="7B61FF")
        cell.alignment = Alignment(horizontal="center")
    for r in rows:
        ws.append([r["date"], r["text"], r["views"], r["forwards"], r["reactions"], r["comments"], r["link"]])
    # автоширина (приблизительно)
    widths = [18, 70, 12, 12, 12, 14, 50]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[chr(64 + i)].width = w
    # перенос текста для колонки "Текст"
    for row in ws.iter_rows(min_row=2, min_col=2, max_col=2):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "A2"

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", ch.name)[:40]
    filename = f"posts_{safe_name}_{period_days}d.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Локальный TG-коллектор (Telethon на компе юзера) ──────
# Юзер запускает локальный скрипт раз в неделю, он:
# 1. GET /api/stats/tg/sync/channels - забирает список своих TG-каналов
# 2. Через Telethon тянет посты каждого канала за период
# 3. POST /api/stats/tg/sync/push - пушит метрики обратно
# Авторизация - заголовок X-Collector-Token (значение из settings.tg_collector_token).

def _require_collector_token(x_collector_token: Optional[str]):
    if not settings.tg_collector_token:
        raise HTTPException(500, "TG collector token не настроен на сервере")
    if x_collector_token != settings.tg_collector_token:
        raise HTTPException(403, "Bad token")


class SyncChannel(BaseModel):
    channel_id: int
    name: str
    username: str  # без @


class SyncChannelsResponse(BaseModel):
    channels: List[SyncChannel]


@router.get("/tg/sync/channels", response_model=SyncChannelsResponse)
def tg_sync_channels(
    x_collector_token: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """Локальный коллектор зовёт этот endpoint, получает список TG-каналов
    для которых надо собрать стату."""
    _require_collector_token(x_collector_token)
    channels = db.query(Channel).filter(
        Channel.platform == Platform.tg,
        Channel.is_active == True,
    ).all()
    result: List[SyncChannel] = []
    for ch in channels:
        raw = (ch.config_json or {}).get("channel") or ""
        username = raw
        if "t.me/" in username:
            username = username.split("t.me/", 1)[1]
        username = username.lstrip("@").strip("/").split("/")[0]
        if not username or username.startswith("+") or username.startswith("joinchat"):
            continue
        result.append(SyncChannel(channel_id=ch.id, name=ch.name, username=username))
    return SyncChannelsResponse(channels=result)


class SyncPostIn(BaseModel):
    message_id: int
    published_at: datetime
    text: str = ""
    views: int = 0
    forwards: int = 0
    reactions: int = 0
    comments: int = 0
    link: str = ""


class SyncPushIn(BaseModel):
    channel_id: int
    subscribers: int = 0
    posts: List[SyncPostIn]


@router.post("/tg/sync/push")
def tg_sync_push(
    data: SyncPushIn,
    x_collector_token: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """Принимает посты + метрики от локального коллектора, пишет в БД (upsert по message_id).
    Также создаёт ChannelSnapshot с подписчиками и агрегатами."""
    _require_collector_token(x_collector_token)
    ch = db.get(Channel, data.channel_id)
    if not ch:
        raise HTTPException(404, "Channel not found")
    if ch.platform != Platform.tg:
        raise HTTPException(400, "Channel is not TG")

    # upsert постов
    posts_upserted = 0
    for p in data.posts:
        existing = db.query(ChannelPost).filter(
            ChannelPost.channel_id == ch.id,
            ChannelPost.message_id == p.message_id,
        ).first()
        if existing:
            existing.text = (p.text or "")[:1000]
            existing.published_at = p.published_at
            existing.views = p.views
            existing.forwards = p.forwards
            existing.reactions = p.reactions
            existing.comments = p.comments
            existing.link = p.link
            existing.updated_at = datetime.now()
        else:
            db.add(ChannelPost(
                channel_id=ch.id,
                message_id=p.message_id,
                text=(p.text or "")[:1000],
                published_at=p.published_at,
                views=p.views,
                forwards=p.forwards,
                reactions=p.reactions,
                comments=p.comments,
                link=p.link,
                updated_at=datetime.now(),
            ))
        posts_upserted += 1

    # снапшот канала с агрегатами
    if data.posts:
        avg_views = sum(p.views for p in data.posts) // max(len(data.posts), 1)
        avg_likes = sum(p.reactions for p in data.posts) // max(len(data.posts), 1)
        avg_reposts = sum(p.forwards for p in data.posts) // max(len(data.posts), 1)
        avg_comments = sum(p.comments for p in data.posts) // max(len(data.posts), 1)
    else:
        avg_views = avg_likes = avg_reposts = avg_comments = 0

    db.add(ChannelSnapshot(
        channel_id=ch.id,
        captured_at=datetime.now(),
        subscribers=data.subscribers,
        avg_views=avg_views,
        avg_likes=avg_likes,
        avg_reposts=avg_reposts,
        avg_comments=avg_comments,
        posts_total=len(data.posts),
    ))
    db.commit()
    return {"ok": True, "posts_upserted": posts_upserted}


# ── Серверный Telethon-сборщик (через SOCKS5/xray) ──────
# Сборщик прямо на сервере цепляется к TG через локальный SOCKS-туннель.
# Кнопка в UI зовёт этот эндпоинт - юзеру не нужно ничего запускать локально.

@router.get("/tg/embed/{username}/{msg_id}")
async def tg_embed_proxy(username: str, msg_id: int):
    """Прокси для t.me/.../embed - чтобы превью грузилось у пользователей без своего VPN.
    Сервер тянет HTML через xray (TG_PROXY_URL), переписывает все ассеты на наш asset-прокси,
    отдаёт клиенту."""
    import re as _re
    from fastapi.responses import HTMLResponse
    import httpx
    from publishers.telegram import _httpx_kwargs

    url = f"https://t.me/{username}/{msg_id}?embed=1&userpic=true&dark=1"
    try:
        async with httpx.AsyncClient(**_httpx_kwargs(15), follow_redirects=True) as client:
            r = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
    except Exception as e:
        raise HTTPException(502, f"upstream fetch failed: {e}")

    if r.status_code != 200:
        raise HTTPException(r.status_code, "t.me returned non-200")

    html = r.text

    # переписываем относительные ссылки на абсолютные t.me, потом ВСЕ t.me/CDN-ссылки -
    # на наш asset-прокси /api/stats/tg/asset?url=<encoded>
    html = html.replace('href="/', 'href="https://t.me/')
    html = html.replace('src="/', 'src="https://t.me/')

    def _rewrite_url(m):
        attr, q, raw = m.group(1), m.group(2), m.group(3)
        # пропускаем data:, blob:, #anchor
        if raw.startswith(('data:', 'blob:', '#', 'javascript:')):
            return m.group(0)
        from urllib.parse import quote
        return f'{attr}={q}/api/stats/tg/asset?url={quote(raw, safe="")}{q}'

    # src="..." и background:url(...) - только https://
    html = _re.sub(r'(src|href)=(")(https://[^"]+)"', _rewrite_url, html)
    html = _re.sub(r'(src|href)=(\')(https://[^\']+)\'', _rewrite_url, html)

    # инжектим наш CSS чтоб превью выглядело адекватно: убираем рамки от t.me,
    # ставим читаемые шрифты и нормальный фон
    css_override = """
    <style>
      html, body { background: #14151a !important; margin: 0 !important; padding: 12px !important; color: #e8eaed !important; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important; }
      .tgme_widget_message_wrap, .tgme_widget_message { background: #1d1f27 !important; border-radius: 12px !important; box-shadow: none !important; border: 1px solid #2a2d38 !important; padding: 14px !important; max-width: 100% !important; }
      .tgme_widget_message_author_name, a, a:visited { color: #8ab4ff !important; }
      .tgme_widget_message_text { color: #e8eaed !important; line-height: 1.5 !important; font-size: 15px !important; }
      .tgme_widget_message_footer, .tgme_widget_message_info { color: #9aa0a6 !important; }
      .tgme_widget_message_bubble_tail, .tgme_widget_message_user { display: none !important; }
      ::-webkit-scrollbar { width: 8px; }
      ::-webkit-scrollbar-thumb { background: #2a2d38; border-radius: 4px; }
    </style>
    """
    if "</head>" in html:
        html = html.replace("</head>", css_override + "</head>", 1)
    else:
        html = css_override + html

    return HTMLResponse(content=html, status_code=200, headers={
        "Cache-Control": "public, max-age=300",
        "Content-Security-Policy": "frame-ancestors 'self'",
    })


@router.get("/tg/asset")
async def tg_asset_proxy(url: str):
    """Скачивает картинку/css/js с t.me или CDN через xray и отдаёт клиенту.
    Юзеру не нужен VPN - всё качается серверным каналом."""
    from fastapi.responses import Response
    import httpx
    from publishers.telegram import _httpx_kwargs

    # Минимальная защита: разрешаем только telegram-домены
    allowed = (
        "t.me", "telegram.org", "telesco.pe", "cdn-telegram.org",
    )
    from urllib.parse import urlparse
    host = (urlparse(url).hostname or "").lower()
    if not any(host == d or host.endswith("." + d) for d in allowed):
        raise HTTPException(400, "host not allowed")

    try:
        async with httpx.AsyncClient(**_httpx_kwargs(15), follow_redirects=True) as client:
            r = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
    except Exception as e:
        raise HTTPException(502, f"upstream fetch failed: {e}")

    if r.status_code != 200:
        raise HTTPException(r.status_code, "upstream non-200")

    ctype = r.headers.get("content-type", "application/octet-stream")
    return Response(
        content=r.content,
        media_type=ctype,
        headers={"Cache-Control": "public, max-age=3600"},
    )


def _period_days_from(since_date: Optional[str], until_date: Optional[str], default: int = 30) -> int:
    """Юзер может задать диапазон дат вместо period_days. Считаем разницу и + запас
    до 'сегодня', т.к. коллекторы фильтруют 'опубликовано за N дней от now'."""
    if not since_date:
        return default
    try:
        since = datetime.strptime(since_date, "%Y-%m-%d")
    except ValueError:
        return default
    # для since считаем от сегодня, чтобы гарантированно захватить нужный диапазон
    delta = (datetime.now() - since).days + 1
    return max(1, min(delta, 365))


@router.post("/tt/collect-now")
async def tt_collect_now(
    period_days: int = Query(30, ge=1, le=365),
    since_date: Optional[str] = Query(None, description="YYYY-MM-DD, приоритетнее period_days"),
    until_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    """Собирает статистику всех активных TT-каналов через RapidAPI (TikTok API 23).
    Идёт через SOCKS5, пишет в channel_posts + channel_snapshots."""
    from services.tt_collector import collect_all_tt_channels
    effective = _period_days_from(since_date, until_date, period_days)
    result = await collect_all_tt_channels(db, period_days=effective)
    if not result.get("ok"):
        raise HTTPException(500, result.get("error", "TT-сбор не удался"))
    return result


@router.post("/tg/collect-now")
async def tg_collect_now(
    period_days: int = Query(30, ge=1, le=365),
    since_date: Optional[str] = Query(None, description="YYYY-MM-DD, приоритетнее period_days"),
    until_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    """Собирает статистику всех активных TG-каналов через Telethon на сервере.
    Идёт через SOCKS5 (TG_PROXY_URL), пишет в channel_posts + channel_snapshots."""
    from services.tg_telethon_collector import collect_all_tg_channels, is_configured
    if not is_configured():
        raise HTTPException(500, "Telethon на сервере не настроен (TELETHON_API_ID/HASH/SESSION_STRING)")
    effective = _period_days_from(since_date, until_date, period_days)
    result = await collect_all_tg_channels(db, period_days=effective)
    if not result.get("ok"):
        raise HTTPException(500, result.get("error", "Сбор не удался"))
    return result


class ChannelTotalItem(BaseModel):
    channel_id: int
    name: str
    platform: str
    posts_count: int
    total_views: int
    total_likes: int
    total_reposts: int
    total_comments: int


@router.get("/channel-totals", response_model=List[ChannelTotalItem])
def channel_totals(
    since_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    until_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    period_days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """Сумма метрик по каждому каналу за период. VK - через PostTarget+PostStats,
    TG/TT - через ChannelPost (там уже все посты канала)."""
    if since_date:
        try:
            since = datetime.strptime(since_date, "%Y-%m-%d")
        except ValueError:
            since = datetime.now() - timedelta(days=period_days)
    else:
        since = datetime.now() - timedelta(days=period_days)

    if until_date:
        try:
            until = datetime.strptime(until_date, "%Y-%m-%d") + timedelta(days=1)
        except ValueError:
            until = datetime.now()
    else:
        until = datetime.now()

    result: Dict[int, Dict] = {}

    # Все платформы (TG/TT/VK) - берём из channel_posts (сборщики каждой платформы
    # пишут туда все посты канала, не только через наш сервис)
    cps = db.query(ChannelPost).join(Channel).filter(
        Channel.is_active == True,
        ChannelPost.published_at >= since,
        ChannelPost.published_at < until,
    ).all()
    for cp in cps:
        ch = cp.channel
        if not ch:
            continue
        agg = result.setdefault(ch.id, {
            "channel_id": ch.id, "name": ch.name, "platform": ch.platform.value,
            "posts_count": 0, "total_views": 0, "total_likes": 0,
            "total_reposts": 0, "total_comments": 0,
        })
        agg["posts_count"] += 1
        agg["total_views"] += int(cp.views or 0)
        agg["total_likes"] += int(cp.reactions or 0)
        agg["total_reposts"] += int(cp.forwards or 0)
        agg["total_comments"] += int(cp.comments or 0)

    items = list(result.values())
    items.sort(key=lambda x: x["total_views"], reverse=True)
    return items
