"""
采集服务 — 封装现有 crawler 模块，返回结构化数据供 task_executor 入库。
"""
import asyncio
import random
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.async_api import async_playwright
from utils.browser import launch_browser, create_context, apply_stealth
from utils.image import download_images_batch
from config import (
    TAOBAO_STATE_FILE, BROWSER_CHANNEL, BROWSER_ARGS,
    IMAGE_ROOT, TMALL_SELECTORS, PARAM_FIELDS,
    DOWNLOAD_HEADERS, MAX_CONCURRENT_DOWNLOADS,
)


async def crawl_single_url(url: str, source: str = "tmall") -> dict:
    """采集单个 URL，返回商品数据字典"""
    async with async_playwright() as p:
        browser = await launch_browser(p, channel=BROWSER_CHANNEL, args=BROWSER_ARGS)

        state_file = TAOBAO_STATE_FILE if source in ("tmall", "taobao") else None
        context = await create_context(browser, state_file=state_file, stealth=True)
        page = await context.new_page()
        await apply_stealth(page)

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(random.uniform(2, 4))

            title_selector = TMALL_SELECTORS["title"]
            try:
                await page.wait_for_selector(title_selector, timeout=15000)
            except Exception:
                for _ in range(60):
                    if await page.query_selector(title_selector):
                        break
                    await asyncio.sleep(1)
                else:
                    raise TimeoutError("等待商品标题超时")

            title_el = await page.query_selector(title_selector)
            title = (await title_el.inner_text()).strip() if title_el else "未知"

            price = ""
            for price_sel in ["price_platform", "price_shop", "price_fallback"]:
                price_el = await page.query_selector(TMALL_SELECTORS[price_sel])
                if price_el:
                    price = (await price_el.inner_text()).strip()
                    break

            params = {}
            param_els = await page.query_selector_all(TMALL_SELECTORS["param_general"])
            for el in param_els:
                try:
                    t = await el.query_selector(TMALL_SELECTORS["param_general_title"])
                    v = await el.query_selector(TMALL_SELECTORS["param_general_value"])
                    if t and v:
                        tk = (await t.inner_text()).strip()
                        vv = (await v.inner_text()).strip()
                        for field in PARAM_FIELDS:
                            if field in tk:
                                params[field] = vv
                                break
                except Exception:
                    continue

            emphasis_els = await page.query_selector_all(TMALL_SELECTORS["param_emphasis"])
            for el in emphasis_els:
                try:
                    t = await el.query_selector(TMALL_SELECTORS["param_emphasis_title"])
                    v = await el.query_selector(TMALL_SELECTORS["param_emphasis_value"])
                    if not t or not v:
                        t = await el.query_selector(TMALL_SELECTORS["param_emphasis_value"])
                        v = await el.query_selector(TMALL_SELECTORS["param_emphasis_title"])
                    if t and v:
                        tk = (await t.inner_text()).strip()
                        vv = (await v.inner_text()).strip()
                        for field in PARAM_FIELDS:
                            if field in tk:
                                params[field] = vv
                                break
                except Exception:
                    continue

            image_paths = await download_images_batch(
                page, title, IMAGE_ROOT, TMALL_SELECTORS,
                DOWNLOAD_HEADERS, MAX_CONCURRENT_DOWNLOADS,
            )

            return {
                "title": title,
                "price": price,
                "style": params.get("风格", ""),
                "color": params.get("颜色分类", "").replace(",", " ").replace("，", " "),
                "season": params.get("适用季节", ""),
                "material": params.get("材质成分", ""),
                "fabric": params.get("面料", ""),
                "safety_level": params.get("安全等级", ""),
                "height": params.get("身高", ""),
                "gender": params.get("适用性别", ""),
                "main_images": image_paths.get("main", ""),
                "sku_images": image_paths.get("sku", ""),
            }
        finally:
            await browser.close()
