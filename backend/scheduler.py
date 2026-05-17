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
            await publish_post(post, db)
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
    # stats jobs
    scheduler.add_job(collect_post_stats, "interval", minutes=15, id="stats_posts_job", next_run_time=datetime.now())
    scheduler.add_job(collect_subscribers, "interval", hours=1, id="stats_subs_job", next_run_time=datetime.now())
    scheduler.start()


def stop_scheduler():
    scheduler.shutdown(wait=False)
