import json
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from server.database import get_db
from server.models import Task, TaskItem

router = APIRouter()


class TaskItemOut(BaseModel):
    id: int
    product_id: Optional[int]
    platform: str
    url: str
    status: str
    error_msg: str

    model_config = {"from_attributes": True}


class TaskOut(BaseModel):
    id: int
    type: str
    status: str
    schedule_type: str
    cron_expr: str
    scheduled_at: Optional[datetime]
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    config_json: str
    result_json: str
    created_at: datetime
    items: list[TaskItemOut] = []

    model_config = {"from_attributes": True}


class TaskListOut(BaseModel):
    total: int
    items: list[TaskOut]


class CrawlTaskCreate(BaseModel):
    urls: list[str]
    source: str = ""  # 为空时根据 URL 自动识别平台
    schedule_type: str = "immediate"
    cron_expr: str = ""
    scheduled_at: Optional[datetime] = None


class UploadTaskCreate(BaseModel):
    product_ids: list[int]
    platforms: list[str]
    schedule_type: str = "immediate"
    cron_expr: str = ""
    scheduled_at: Optional[datetime] = None


@router.get("", response_model=TaskListOut)
async def list_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    type: str = Query("", description="任务类型: crawl/upload"),
    status: str = Query("", description="状态筛选"),
    db: AsyncSession = Depends(get_db),
):
    query = select(Task).options(selectinload(Task.items))
    count_query = select(func.count(Task.id))

    if type:
        query = query.where(Task.type == type)
        count_query = count_query.where(Task.type == type)
    if status:
        query = query.where(Task.status == status)
        count_query = count_query.where(Task.status == status)

    total = (await db.execute(count_query)).scalar() or 0
    items = (
        await db.execute(
            query.order_by(desc(Task.created_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().unique().all()

    return TaskListOut(total=total, items=items)


@router.get("/{task_id}", response_model=TaskOut)
async def get_task(task_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Task).options(selectinload(Task.items)).where(Task.id == task_id)
    )
    task = result.scalars().first()
    if not task:
        raise HTTPException(404, "任务不存在")
    return task


@router.post("/crawl", response_model=TaskOut)
async def create_crawl_task(body: CrawlTaskCreate, db: AsyncSession = Depends(get_db)):
    task = Task(
        type="crawl",
        status="pending",
        schedule_type=body.schedule_type,
        cron_expr=body.cron_expr,
        scheduled_at=body.scheduled_at,
        config_json=json.dumps({"source": body.source}, ensure_ascii=False),
    )
    for url in body.urls:
        task.items.append(TaskItem(url=url, status="pending"))
    db.add(task)
    await db.commit()

    result = await db.execute(
        select(Task).options(selectinload(Task.items)).where(Task.id == task.id)
    )
    task = result.scalars().first()

    if body.schedule_type == "immediate":
        from server.services.task_executor import execute_task_background
        execute_task_background(task.id)
    elif body.schedule_type == "once" and body.scheduled_at:
        from server.services.scheduler_service import schedule_once
        schedule_once(task.id, body.scheduled_at)
    elif body.schedule_type == "cron" and body.cron_expr:
        from server.services.scheduler_service import schedule_cron
        schedule_cron(task.id, body.cron_expr)

    return task


@router.post("/upload", response_model=TaskOut)
async def create_upload_task(body: UploadTaskCreate, db: AsyncSession = Depends(get_db)):
    task = Task(
        type="upload",
        status="pending",
        schedule_type=body.schedule_type,
        cron_expr=body.cron_expr,
        scheduled_at=body.scheduled_at,
        config_json=json.dumps({"platforms": body.platforms}, ensure_ascii=False),
    )
    for pid in body.product_ids:
        for platform in body.platforms:
            task.items.append(TaskItem(product_id=pid, platform=platform, status="pending"))
    db.add(task)
    await db.commit()

    result = await db.execute(
        select(Task).options(selectinload(Task.items)).where(Task.id == task.id)
    )
    task = result.scalars().first()

    if body.schedule_type == "immediate":
        from server.services.task_executor import execute_task_background
        execute_task_background(task.id)
    elif body.schedule_type == "once" and body.scheduled_at:
        from server.services.scheduler_service import schedule_once
        schedule_once(task.id, body.scheduled_at)
    elif body.schedule_type == "cron" and body.cron_expr:
        from server.services.scheduler_service import schedule_cron
        schedule_cron(task.id, body.cron_expr)

    return task


@router.put("/{task_id}/cancel")
async def cancel_task(task_id: int, db: AsyncSession = Depends(get_db)):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    if task.status in ("done", "failed"):
        raise HTTPException(400, "任务已结束，无法取消")

    task.status = "cancelled"
    await db.commit()

    from server.services.scheduler_service import remove_job
    remove_job(task_id)

    return {"message": "已取消"}
