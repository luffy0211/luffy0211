from datetime import datetime, time
from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy import select, func, and_, desc, or_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from server.database import get_db
from server.models import Product, Task, TaskItem

router = APIRouter()


class DashboardStats(BaseModel):
    total_products: int
    today_crawl: int
    today_upload: int
    pending_tasks: int


class RecentTaskOut(BaseModel):
    id: int
    type: str
    status: str
    created_at: datetime
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    total_items: int
    success_items: int
    failed_items: int
    errors: list[str]

    model_config = {"from_attributes": True}


@router.get("/stats", response_model=DashboardStats)
async def get_stats(db: AsyncSession = Depends(get_db)):
    today_start = datetime.combine(datetime.now().date(), time.min)

    total_products = (
        await db.execute(select(func.count(Product.id)))
    ).scalar() or 0

    today_crawl = (
        await db.execute(
            select(func.count(Product.id)).where(
                Product.crawled_at >= today_start
            )
        )
    ).scalar() or 0

    today_upload = (
        await db.execute(
            select(func.count(TaskItem.id)).where(
                and_(
                    TaskItem.status == "success",
                    TaskItem.platform != "",
                    TaskItem.platform.is_not(None),
                )
            )
        )
    ).scalar() or 0

    pending_tasks = (
        await db.execute(
            select(func.count(Task.id)).where(
                Task.status.in_(["pending", "running"])
            )
        )
    ).scalar() or 0

    return DashboardStats(
        total_products=total_products,
        today_crawl=today_crawl,
        today_upload=today_upload,
        pending_tasks=pending_tasks,
    )


@router.get("/recent-activities", response_model=list[RecentTaskOut])
async def get_recent_activities(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Task)
        .options(selectinload(Task.items))
        .order_by(desc(Task.created_at))
        .limit(10)
    )
    tasks = result.scalars().unique().all()

    out = []
    for t in tasks:
        total = len(t.items)
        success = sum(1 for i in t.items if i.status == "success")
        failed = sum(1 for i in t.items if i.status == "failed")
        errors = [
            f"{i.url or ('商品#' + str(i.product_id))}{(' → ' + i.platform) if i.platform else ''}: {i.error_msg}"
            for i in t.items
            if i.status == "failed" and i.error_msg
        ]
        out.append(RecentTaskOut(
            id=t.id,
            type=t.type,
            status=t.status,
            created_at=t.created_at,
            started_at=t.started_at,
            finished_at=t.finished_at,
            total_items=total,
            success_items=success,
            failed_items=failed,
            errors=errors,
        ))
    return out
