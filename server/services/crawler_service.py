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
from utils.image import download_images_batch, sanitize_filename, download_image
from config import (
    TAOBAO_STATE_FILE, E3E3_STATE_FILE,
    BROWSER_CHANNEL, BROWSER_ARGS,
    IMAGE_ROOT, TMALL_SELECTORS, PARAM_FIELDS,
    DOWNLOAD_HEADERS, MAX_CONCURRENT_DOWNLOADS,
)

import logging
logger = logging.getLogger("crawler_service")


async def crawl_single_url(url: str, source: str = "tmall") -> dict:
    """采集单个 URL，根据 source 分发到不同采集逻辑"""
    if source == "3e3e":
        return await crawl_3e3e_url(url)
    else:
        return await crawl_tmall_url(url, source)


async def crawl_tmall_url(url: str, source: str = "tmall") -> dict:
    """采集天猫/淘宝商品"""
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


async def crawl_3e3e_url(url: str) -> dict:
    """采集 3e3e 平台商品"""
    async with async_playwright() as p:
        browser = await launch_browser(p, channel=BROWSER_CHANNEL, args=BROWSER_ARGS, headless=True)

        state_file = E3E3_STATE_FILE if os.path.exists(E3E3_STATE_FILE) else None
        context = await create_context(browser, state_file=state_file, stealth=True)
        page = await context.new_page()

        try:
            await page.goto(url, timeout=60000)
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(random.uniform(1, 3))

            # 等待商品标题出现
            try:
                await page.wait_for_selector(".product-details h5", timeout=30000)
            except Exception:
                await asyncio.sleep(5)
                title_check = await page.query_selector(".product-details h5")
                if not title_check:
                    raise TimeoutError("等待商品标题超时，页面可能未正确加载或需要登录")

            # 标题
            title_el = await page.query_selector(".product-details h5")
            raw_title = (await title_el.inner_text()).strip() if title_el else "未知"
            title = raw_title.replace("复制", "").replace(" ", "").strip()

            # 价格
            price_el = await page.query_selector(".product-price-info strong i")
            price = (await price_el.inner_text()).strip() if price_el else ""

            # 主图（data-url）
            image_urls = []
            img_els = await page.query_selector_all(".small-img-list img")
            for img in img_els:
                src = await img.get_attribute("data-url")
                if src and src not in image_urls:
                    image_urls.append(src)

            # SKU 图
            sku_img_els = await page.query_selector_all("ul.sku-wrap img")
            for img in sku_img_els:
                src = (await img.get_attribute("src")) or (await img.get_attribute("data-url"))
                if src and src not in image_urls:
                    image_urls.append(src)

            # 颜色
            colors = []
            color_els = await page.query_selector_all(".sku-warp-li")
            for el in color_els:
                color = await el.get_attribute("data-color")
                if color:
                    colors.append(color)

            # 属性
            attrs = {}
            attr_els = await page.query_selector_all(".details-attribute-item")
            for el in attr_els:
                text = (await el.inner_text()).strip()
                if "：" in text:
                    key, value = text.split("：", 1)
                    key = key.strip()
                    value = value.strip()
                    # 去掉可能的分类前缀 "分类： 套装 >"
                    if key == "风格":
                        attrs["风格"] = value
                    elif key == "面料":
                        attrs["面料"] = value
                    elif key == "适用季节":
                        attrs["适用季节"] = value
                    elif key == "材质成分":
                        attrs["材质成分"] = value
                    elif key in ("安全类别", "安全等级"):
                        attrs["安全等级"] = value
                    elif key == "身高":
                        attrs["身高"] = value
                    elif key == "适用性别":
                        attrs["适用性别"] = value
                    elif key == "颜色分类":
                        attrs["颜色分类"] = value

            # 区分主图 / SKU图并下载
            main_urls = [u for u in image_urls if u.startswith("https")]
            sku_urls = [u for u in image_urls if u.startswith("http") and not u.startswith("https")]

            safe_name = sanitize_filename(title)
            product_folder = os.path.join(IMAGE_ROOT, safe_name)
            sku_folder = os.path.join(product_folder, "sku")
            os.makedirs(product_folder, exist_ok=True)
            os.makedirs(sku_folder, exist_ok=True)

            import aiohttp
            headers_3e3e = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://www.3e3e.cn/",
            }
            semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)

            async with aiohttp.ClientSession() as session:
                # 下载主图
                main_tasks = []
                main_paths = []
                for i, src in enumerate(main_urls):
                    ext = ".png" if ".png" in src else ".jpg"
                    filepath = os.path.join(product_folder, f"{safe_name}_主图_{i+1}{ext}")
                    main_paths.append(filepath)
                    main_tasks.append(download_image(session, src, filepath, headers_3e3e, semaphore))

                main_results = await asyncio.gather(*main_tasks, return_exceptions=True)
                success_main = [p for p, r in zip(main_paths, main_results) if r is True]

                # 下载 SKU 图
                sku_tasks = []
                sku_paths = []
                for i, src in enumerate(sku_urls):
                    ext = ".png" if ".png" in src else ".jpg"
                    filepath = os.path.join(sku_folder, f"{safe_name}_SKU_{i+1}{ext}")
                    sku_paths.append(filepath)
                    sku_tasks.append(download_image(session, src, filepath, headers_3e3e, semaphore))

                sku_results = await asyncio.gather(*sku_tasks, return_exceptions=True)
                success_sku = [p for p, r in zip(sku_paths, sku_results) if r is True]

            logger.info(f"[3e3e] 图片下载完成 主图:{len(success_main)} SKU:{len(success_sku)}")

            color_str = " ".join(colors) if colors else attrs.get("颜色分类", "")

            return {
                "title": title,
                "price": price,
                "style": attrs.get("风格", ""),
                "color": color_str.replace(",", " ").replace("，", " "),
                "season": attrs.get("适用季节", ""),
                "material": attrs.get("材质成分", ""),
                "fabric": attrs.get("面料", ""),
                "safety_level": attrs.get("安全等级", ""),
                "height": attrs.get("身高", ""),
                "gender": attrs.get("适用性别", ""),
                "main_images": "; ".join(success_main),
                "sku_images": "; ".join(success_sku),
            }
        finally:
            await browser.close()
