import asyncio
import os
import sys
import random
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.async_api import async_playwright
from utils.browser import launch_browser, create_context, apply_stealth
from utils.excel import read_urls, write_product_data
from utils.image import download_images_batch
from utils.logger import setup_logger
from config import (
    TAOBAO_STATE_FILE, BROWSER_CHANNEL, BROWSER_ARGS,
    URLS_EXCEL, OUTPUT_EXCEL, IMAGE_ROOT,
    TMALL_SELECTORS, PARAM_FIELDS, OUTPUT_HEADERS,
    DOWNLOAD_HEADERS, MAX_CONCURRENT_DOWNLOADS,
)

logger = setup_logger("crawler")


async def random_delay(min_sec=1, max_sec=3):
    await asyncio.sleep(random.uniform(min_sec, max_sec))


async def extract_params(page, selectors: dict, fields: list[str]) -> dict:
    """提取商品参数（通用参数 + 强调参数）"""
    params = {}

    # 通用参数
    param_els = await page.query_selector_all(selectors["param_general"])
    for el in param_els:
        try:
            title_el = await el.query_selector(selectors["param_general_title"])
            value_el = await el.query_selector(selectors["param_general_value"])
            if title_el and value_el:
                title = (await title_el.inner_text()).strip()
                value = (await value_el.inner_text()).strip()
                for field in fields:
                    if field in title:
                        params[field] = value
                        break
        except Exception as e:
            logger.debug(f"解析通用参数失败: {e}")
            continue

    # 强调参数
    emphasis_els = await page.query_selector_all(selectors["param_emphasis"])
    for el in emphasis_els:
        try:
            title_el = await el.query_selector(selectors["param_emphasis_title"])
            value_el = await el.query_selector(selectors["param_emphasis_value"])
            if not title_el or not value_el:
                title_el = await el.query_selector(selectors["param_emphasis_value"])
                value_el = await el.query_selector(selectors["param_emphasis_title"])
            if title_el and value_el:
                title = (await title_el.inner_text()).strip()
                value = (await value_el.inner_text()).strip()
                for field in fields:
                    if field in title:
                        params[field] = value
                        break
        except Exception as e:
            logger.debug(f"解析强调参数失败: {e}")
            continue

    return params


async def crawl_single_product(page, product_url: str, index: int):
    """采集单个商品数据"""
    logger.info(f"[{index}] 正在访问: {product_url}")
    await random_delay(1, 2)

    try:
        await page.goto(product_url, wait_until="domcontentloaded", timeout=30000)
        await random_delay(2, 4)
        await page.mouse.move(random.randint(300, 800), random.randint(200, 600))
        await random_delay(0.5, 1.5)

        title_selector = TMALL_SELECTORS["title"]

        try:
            await page.wait_for_selector(title_selector, timeout=15000)
        except Exception:
            logger.warning(f"[{index}] 未发现商品标题，可能需要手动验证...")
            for _ in range(60):
                if await page.query_selector(title_selector):
                    break
                await asyncio.sleep(1)
            else:
                logger.error(f"[{index}] 等待超时，跳过此商品")
                return

        # 标题
        title_el = await page.query_selector(title_selector)
        title = (await title_el.inner_text()).strip() if title_el else "未知"

        # 价格
        price = "未找到价格"
        for price_sel in ["price_platform", "price_shop", "price_fallback"]:
            price_el = await page.query_selector(TMALL_SELECTORS[price_sel])
            if price_el:
                price = (await price_el.inner_text()).strip()
                break

        logger.info(f"[{index}] 商品: {title} | 价格: {price}")

        # 参数
        params = await extract_params(page, TMALL_SELECTORS, PARAM_FIELDS)
        for key in PARAM_FIELDS:
            if params.get(key):
                logger.info(f"  {key}: {params[key]}")

        # 图片
        logger.info(f"[{index}] 正在下载图片...")
        image_paths = await download_images_batch(
            page, title, IMAGE_ROOT, TMALL_SELECTORS,
            DOWNLOAD_HEADERS, MAX_CONCURRENT_DOWNLOADS,
        )

        # 写入 Excel
        write_product_data(
            OUTPUT_EXCEL,
            OUTPUT_HEADERS,
            {
                "商品名称": title,
                "价格": price,
                "商品链接": product_url,
                "抓取时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
            params,
            image_paths,
        )

        logger.info(f"[{index}] 采集完成: {title}")

    except Exception as e:
        logger.error(f"[{index}] 采集失败: {e}")


async def run_crawler():
    """批量采集天猫商品"""
    if not os.path.exists(TAOBAO_STATE_FILE):
        logger.error(f"未找到 {TAOBAO_STATE_FILE}，请先运行 login/taobao_login.py")
        return

    urls = read_urls(URLS_EXCEL)
    if not urls:
        logger.error("无可用 URL，请检查 urls.xlsx")
        return

    logger.info(f"共 {len(urls)} 个商品待采集")

    async with async_playwright() as p:
        browser = await launch_browser(p, channel=BROWSER_CHANNEL, args=BROWSER_ARGS)
        context = await create_context(browser, state_file=TAOBAO_STATE_FILE, stealth=True)
        page = await context.new_page()
        await apply_stealth(page)
        await random_delay(1, 3)

        for i, url in enumerate(urls, 1):
            await crawl_single_product(page, url, i)
            if i < len(urls):
                delay = random.uniform(3, 6)
                logger.info(f"等待 {delay:.1f}秒 后处理下一个...")
                await asyncio.sleep(delay)

        logger.info(f"全部采集完成！共处理 {len(urls)} 个商品")
        await asyncio.sleep(3)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(run_crawler())
