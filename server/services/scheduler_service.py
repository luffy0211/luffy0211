from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from datetime import datetime

scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")


def schedule_once(task_id: int, run_at: datetime):
    from server.services.task_executor import run_task
    job_id = f"task_{task_id}"
    scheduler.add_job(
        run_task,
        trigger=DateTrigger(run_date=run_at),
        args=[task_id],
        id=job_id,
        replace_existing=True,
    )


def schedule_cron(task_id: int, cron_expr: str):
    from server.services.task_executor import run_task
    job_id = f"task_{task_id}"
    parts = cron_expr.strip().split()
    if len(parts) == 5:
        minute, hour, day, month, day_of_week = parts
        scheduler.add_job(
            run_task,
            trigger=CronTrigger(
                minute=minute, hour=hour, day=day, month=month, day_of_week=day_of_week
            ),
            args=[task_id],
            id=job_id,
            replace_existing=True,
        )


def remove_job(task_id: int):
    job_id = f"task_{task_id}"
    try:
        scheduler.remove_job(job_id)
    except Exception:
        pass
