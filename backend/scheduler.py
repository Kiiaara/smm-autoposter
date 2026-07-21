from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from database import SessionLocal
from models.post import Post, PostStatus

scheduler = AsyncIOScheduler()


async def publish_due_posts():
    from services.publish_service import publish_post
    db = SessionLocal()
    try:
        due = db.query(Post).filter(
            Post.status == PostStatus.scheduled,
            Post.scheduled_at <= datetime.now(),
        ).all()
        for post in due:
            # Изолируем каждый пост - если один зависнет или крешнется, остальные всё равно
            # попробуют опубликоваться, и scheduler освободится для следующего тика.
            try:
                await publish_post(post, db)
            except Exception as e:
                print(f"[scheduler] publish_post({post.id}) failed: {e}", flush=True)
    finally:
        db.close()


async def send_due_reminders():
    from services.reminder_service import send_due_reminders as _send
    await _send()


async def collect_post_stats():
    from services.stats_service import run_post_stats_collection
    await run_post_stats_collection()


async def collect_subscribers():
    from services.stats_service import run_subscribers_collection
    await run_subscribers_collection()


def start_scheduler(interval_seconds: int = 60):
    scheduler.add_job(publish_due_posts, "interval", seconds=interval_seconds, id="publish_job")
    scheduler.add_job(send_due_reminders, "interval", seconds=interval_seconds, id="reminder_job")
    # stats jobs - реже, чтобы экономить TGStat-квоту (500 запросов/день на free)
    scheduler.add_job(collect_post_stats, "interval", hours=2, id="stats_posts_job", next_run_time=datetime.now())
    scheduler.add_job(collect_subscribers, "interval", hours=6, id="stats_subs_job", next_run_time=datetime.now())
    scheduler.start()


def stop_scheduler():
    scheduler.shutdown(wait=False)
