"""
任务执行器 — 在后台线程中运行采集/上架任务，
桥接 FastAPI 与现有 Playwright 模块。
"""
import asyncio
import json
import sys
import threading
import logging
from datetime import datetime

logger = logging.getLogger("task_executor")


def execute_task_background(task_id: int):
    """在新线程中启动一个事件循环来执行任务（避免阻塞主 uvicorn 循环）"""
    def _target():
        if sys.platform.startswith("win"):
            loop = asyncio.ProactorEventLoop()
        else:
            loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(run_task(task_id))
        finally:
            loop.close()

    t = threading.Thread(target=_target, daemon=True)
    t.start()


async def run_task(task_id: int):
    from server.database import async_session
    from server.models import Task, TaskItem
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    async with async_session() as db:
        result = await db.execute(
            select(Task).options(selectinload(Task.items)).where(Task.id == task_id)
        )
        task = result.scalars().first()
        if not task or task.status in ("cancelled", "running"):
            return

        task.status = "running"
        task.started_at = datetime.now()
        await db.commit()

        try:
            if task.type == "crawl":
                await _run_crawl(db, task)
            elif task.type == "upload":
                await _run_upload(db, task)

            task.status = "done"
        except Exception as e:
            logger.exception(f"任务 {task_id} 执行失败")
            task.status = "failed"
            task.result_json = json.dumps({"error": str(e)}, ensure_ascii=False)
        finally:
            task.finished_at = datetime.now()
            await db.commit()


async def _run_crawl(db, task):
    """执行采集任务：逐个 URL 调用现有 crawler"""
    from server.services.crawler_service import crawl_single_url
    from server.models import Product

    config = json.loads(task.config_json) if task.config_json else {}
    source = config.get("source", "tmall")

    for item in task.items:
        if task.status == "cancelled":
            break
        try:
            item.status = "running"
            await db.commit()

            product_data = await crawl_single_url(item.url, source)

            product = Product(
                title=product_data.get("title", ""),
                price=product_data.get("price", ""),
                url=item.url,
                style=product_data.get("style", ""),
                color=product_data.get("color", ""),
                season=product_data.get("season", ""),
                material=product_data.get("material", ""),
                fabric=product_data.get("fabric", ""),
                safety_level=product_data.get("safety_level", ""),
                height=product_data.get("height", ""),
                gender=product_data.get("gender", ""),
                main_images=product_data.get("main_images", ""),
                sku_images=product_data.get("sku_images", ""),
                source=source,
                status="crawled",
                crawled_at=datetime.now(),
            )
            db.add(product)
            item.product_id = product.id
            item.status = "success"
        except Exception as e:
            logger.error(f"采集失败 [{item.url}]: {e}")
            item.status = "failed"
            item.error_msg = str(e)
        finally:
            await db.commit()


async def _run_upload(db, task):
    """执行上架任务：委托给 uploader_service 按平台批量执行"""
    from server.services.uploader_service import run_upload_batch
    await run_upload_batch(db, task)
