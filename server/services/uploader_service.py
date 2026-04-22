"""
上架服务 — 按平台分组，启动浏览器，逐条调用各 uploader 的 process_single_item。
"""
import asyncio
import importlib
import logging
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from playwright.async_api import async_playwright
from utils.browser import launch_browser, create_context, handle_popups
from config import (
    WEIXIN_STATE_FILE, SHIPINHAO_STATE_FILE, XHS_STATE_FILE, DOUDIAN_STATE_FILE,
    BROWSER_CHANNEL,
    WEIXIN_GOODS_URL, WEIXIN_MICRO_APP,
    SHIPINHAO_GOODS_URL, SHIPINHAO_MICRO_APP,
    XHS_GOODS_URL,
    DOUDIAN_GOODS_URL,
)

logger = logging.getLogger("uploader_service")

PLATFORM_CONFIG = {
    "weixin": {
        "state_file": WEIXIN_STATE_FILE,
        "goods_url": WEIXIN_GOODS_URL,
        "micro_app": WEIXIN_MICRO_APP,
        "module": "uploader.weixin_uploader",
    },
    "shipinhao": {
        "state_file": SHIPINHAO_STATE_FILE,
        "goods_url": SHIPINHAO_GOODS_URL,
        "micro_app": SHIPINHAO_MICRO_APP,
        "module": "uploader.shipinhao_uploader",
    },
    "xhs": {
        "state_file": XHS_STATE_FILE,
        "goods_url": XHS_GOODS_URL,
        "micro_app": None,
        "module": "uploader.xiaohongshu_uploader",
    },
    "doudian": {
        "state_file": DOUDIAN_STATE_FILE,
        "goods_url": DOUDIAN_GOODS_URL,
        "micro_app": None,
        "module": "uploader.doudian_uploader",
    },
}


def _build_item_dict(product) -> dict:
    """将 Product ORM 对象转为 uploader 期望的 item dict

    - main_images / sku_images 存的是分号分隔的文件路径列表
    - uploader 需要的 image_path 是主图所在的文件夹路径
    - uploader 需要的 color_image_paths 是 SKU 图所在的文件夹路径
    """
    main_images = product.main_images or ""
    sku_images = product.sku_images or ""

    # 从第一张主图路径推导出文件夹
    image_folder = ""
    if main_images:
        first_path = main_images.split(";")[0].strip()
        if first_path and os.path.exists(first_path):
            image_folder = os.path.dirname(first_path)

    # 从第一张 SKU 图路径推导出文件夹
    sku_folder = ""
    if sku_images:
        first_sku = sku_images.split(";")[0].strip()
        if first_sku and os.path.exists(first_sku):
            sku_folder = os.path.dirname(first_sku)

    return {
        "title": product.title or "",
        "price": product.price or "",
        "sale_price": product.price or "",
        "image_path": image_folder,
        "color": product.color or "",
        "style": product.style or "",
        "material": product.material or "",
        "material_composition": product.material or "",
        "fabric": product.fabric or "",
        "safety_level": product.safety_level or "",
        "season": product.season or "",
        "sizes": product.height or "",
        "color_image_paths": sku_folder,
    }


def _get_process_func(module_path: str):
    """动态导入 uploader 模块并返回 process_single_item 函数"""
    mod = importlib.import_module(module_path)
    return mod.process_single_item


async def run_upload_batch(db, task):
    """执行上架任务：按平台分组，每个平台启动一次浏览器，逐条上架"""
    from server.models import Product, TaskItem

    groups = defaultdict(list)
    for item in task.items:
        if item.platform:
            groups[item.platform].append(item)

    for platform, items in groups.items():
        config = PLATFORM_CONFIG.get(platform)
        if not config:
            for item in items:
                item.status = "failed"
                item.error_msg = f"不支持的平台: {platform}"
                await db.commit()
            continue

        state_file = config["state_file"]
        if not os.path.exists(state_file):
            for item in items:
                item.status = "failed"
                item.error_msg = f"未找到登录状态文件，请先登录 {platform}"
                await db.commit()
            continue

        process_single_item = _get_process_func(config["module"])
        goods_url = config["goods_url"]
        micro_app = config.get("micro_app")

        async with async_playwright() as p:
            browser = await launch_browser(p, channel=BROWSER_CHANNEL)
            context = await create_context(browser, state_file=state_file, no_viewport=True)

            for idx, item in enumerate(items, 1):
                if task.status == "cancelled":
                    break

                page = await context.new_page()
                try:
                    item.status = "running"
                    await db.commit()

                    product = await db.get(Product, item.product_id)
                    if not product:
                        item.status = "failed"
                        item.error_msg = f"商品 {item.product_id} 不存在"
                        await db.commit()
                        await page.close()
                        continue

                    item_dict = _build_item_dict(product)
                    logger.info(f"[{platform}] 上架第 {idx}/{len(items)} 条: {product.title}")

                    await page.goto(goods_url, wait_until="domcontentloaded")
                    await asyncio.sleep(3)
                    await handle_popups(page)

                    if micro_app:
                        try:
                            await page.wait_for_selector(micro_app, timeout=20000)
                        except Exception:
                            logger.warning(f"[{platform}] 微应用加载超时，继续尝试")

                    result = await process_single_item(page, item_dict, idx)

                    if result is False or result is None:
                        item.status = "failed"
                        item.error_msg = "process_single_item 返回失败"
                    else:
                        item.status = "success"

                except Exception as e:
                    logger.error(f"[{platform}] 上架失败 [product={item.product_id}]: {e}")
                    item.status = "failed"
                    item.error_msg = str(e)[:500]
                finally:
                    try:
                        await page.close()
                    except Exception:
                        pass
                    await db.commit()

                if idx < len(items):
                    await asyncio.sleep(2)

            await browser.close()
            logger.info(f"[{platform}] 浏览器已关闭，完成 {len(items)} 条商品上架")
