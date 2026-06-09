import io
import re
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from pydantic import BaseModel
from database import get_db
from models.post import Post, PostTarget, PostTargetStatus
from models.channel import Channel, Platform
from models.stats import PostStats, ChannelSnapshot

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
    total_views: int
    total_likes: int


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

    # TG: тянем метрики наших TG-таргетов из TGStat (в БД их нет)
    # Кешируем посты канала за запрос - вместо отдельного запроса на каждый таргет
    tg_posts_cache: Dict[int, Dict[int, dict]] = {}  # channel_id -> {msg_id: post}
    tg_target_ids: set = set()
    from services import tg_stats
    if tg_stats.is_configured():
        from models.channel import Platform as _Plat
        tg_targets = [t for t in targets if t.channel and t.channel.platform == _Plat.tg and t.published_message_id]
        # группируем по каналу
        by_ch: Dict[int, list] = {}
        for t in tg_targets:
            by_ch.setdefault(t.channel_id, []).append(t)
        for ch_id, ts in by_ch.items():
            ch = ts[0].channel
            try:
                posts = await tg_stats.fetch_channel_posts(ch, limit=100, period_days=period_days)
                tg_posts_cache[ch_id] = {int(p.get("id") or p.get("message_id") or 0): p for p in posts}
            except Exception:
                tg_posts_cache[ch_id] = {}

    def _tg_metrics_for_target(t: PostTarget):
        """Возвращает (views, likes, reposts, comments) для TG-таргета из кеша TGStat."""
        if not t.channel or t.channel.platform.value != "tg":
            return None
        cache = tg_posts_cache.get(t.channel_id) or {}
        try:
            msg_id = int(t.published_message_id) if t.published_message_id else None
        except (ValueError, TypeError):
            return None
        if not msg_id:
            return None
        p = cache.get(msg_id)
        if not p:
            return None
        # парсинг как в top_posts
        raw_r = p.get("reactions") or p.get("reactions_count")
        if isinstance(raw_r, dict):
            likes = sum(int(v or 0) for v in raw_r.values())
        elif isinstance(raw_r, list):
            likes = sum(int((r.get("count") or 0) if isinstance(r, dict) else 0) for r in raw_r)
        else:
            likes = int(raw_r or 0)
        raw_c = p.get("comments") or p.get("comments_count")
        if isinstance(raw_c, dict):
            comments = int(raw_c.get("count") or 0)
        else:
            comments = int(raw_c or 0)
        return int(p.get("views") or 0), likes, int(p.get("forwards") or 0), comments

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
            total_views=agg["views"],
            total_likes=agg["likes"],
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

    # TG: тянем посты прямо из TGStat (все посты канала, не только наши)
    if want_tg:
        from services import tg_stats
        if tg_stats.is_configured():
            tg_channels = db.query(Channel).filter(
                Channel.platform == Platform.tg,
                Channel.is_active == True,
            ).all()
            if channel_id:
                tg_channels = [c for c in tg_channels if c.id == channel_id]
            for ch in tg_channels:
                try:
                    posts = await tg_stats.fetch_channel_posts(ch, limit=50, period_days=period_days)
                except Exception:
                    posts = []
                username = (ch.config_json or {}).get("channel") or ""
                # для построения ссылки на пост
                uname = ""
                if "t.me/" in username:
                    uname = username.split("t.me/", 1)[1].strip("/").split("/")[0]
                elif username.startswith("@"):
                    uname = username[1:]
                import re as _re
                def _strip_tags(s: str) -> str:
                    s = _re.sub(r"<[^>]+>", "", s or "")
                    return s.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").strip()
                for p in posts:
                    msg_id = p.get("id") or p.get("message_id")
                    text = _strip_tags(p.get("text") or "")[:160]
                    pub_ts = p.get("date") or p.get("created_at")
                    if isinstance(pub_ts, (int, float)):
                        pub_dt = datetime.fromtimestamp(pub_ts)
                    else:
                        continue
                    if pub_dt < since:
                        continue
                    url = p.get("link") or (f"https://t.me/{uname}/{msg_id}" if uname and msg_id else None)
                    # TGStat может вернуть reactions как число, как объект {emoji: count}, или вообще nil
                    raw_reactions = p.get("reactions") or p.get("reactions_count")
                    if isinstance(raw_reactions, dict):
                        likes_count = sum(int(v or 0) for v in raw_reactions.values())
                    elif isinstance(raw_reactions, list):
                        likes_count = sum(int((r.get("count") or 0) if isinstance(r, dict) else 0) for r in raw_reactions)
                    else:
                        likes_count = int(raw_reactions or 0)
                    # комменты - может быть число или объект с .count
                    raw_comments = p.get("comments") or p.get("comments_count")
                    if isinstance(raw_comments, dict):
                        comments_count = int(raw_comments.get("count") or 0)
                    else:
                        comments_count = int(raw_comments or 0)
                    items.append(TopPostItem(
                        post_id=int(msg_id) if msg_id else 0,
                        title=None,
                        preview=text,
                        platform="tg",
                        channel_name=ch.name,
                        published_at=pub_dt,
                        url=url,
                        views=int(p.get("views") or 0),
                        likes=likes_count,
                        reposts=int(p.get("forwards") or 0),
                        comments=comments_count,
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
        from services import tg_stats
        if not tg_stats.is_configured():
            raise HTTPException(400, "TGStat не настроен")
        try:
            posts = await tg_stats.fetch_channel_posts(ch, limit=200, period_days=period_days)
        except Exception as e:
            raise HTTPException(500, f"TGStat error: {e}")

        # username для построения ссылки
        username = (ch.config_json or {}).get("channel") or ""
        uname = ""
        if "t.me/" in username:
            uname = username.split("t.me/", 1)[1].strip("/").split("/")[0]
        elif username.startswith("@"):
            uname = username[1:]

        for p in posts:
            msg_id = p.get("id") or p.get("message_id")
            pub_ts = p.get("date") or p.get("created_at")
            if not isinstance(pub_ts, (int, float)):
                continue
            pub_dt = datetime.fromtimestamp(pub_ts)
            if pub_dt < since:
                continue
            raw_r = p.get("reactions") or p.get("reactions_count")
            if isinstance(raw_r, dict):
                reactions = sum(int(v or 0) for v in raw_r.values())
            elif isinstance(raw_r, list):
                reactions = sum(int((r.get("count") or 0) if isinstance(r, dict) else 0) for r in raw_r)
            else:
                reactions = int(raw_r or 0)
            raw_c = p.get("comments") or p.get("comments_count")
            if isinstance(raw_c, dict):
                comments = int(raw_c.get("count") or 0)
            else:
                comments = int(raw_c or 0)
            link = p.get("link") or (f"https://t.me/{uname}/{msg_id}" if uname and msg_id else "")
            rows.append({
                "date": pub_dt.strftime("%Y-%m-%d %H:%M"),
                "text": _strip_html(p.get("text") or ""),
                "views": int(p.get("views") or 0),
                "forwards": int(p.get("forwards") or 0),
                "reactions": reactions,
                "comments": comments,
                "link": link,
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
