import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.async_api import async_playwright
from utils.browser import launch_browser, apply_stealth
from utils.logger import setup_logger
from config import TAOBAO_STATE_FILE, BROWSER_CHANNEL, STATE_DIR

logger = setup_logger("taobao_login")


async def login_and_save_state():
    """淘宝扫码登录并保存浏览器状态"""
    os.makedirs(STATE_DIR, exist_ok=True)

    async with async_playwright() as p:
        browser = await launch_browser(p, channel=BROWSER_CHANNEL)
        context = await browser.new_context()
        page = await context.new_page()

        await apply_stealth(page)

        logger.info("正在打开淘宝登录页...")
        await page.goto("https://login.taobao.com/")

        logger.info("请在 120 秒内完成扫码登录！")

        try:
            await page.wait_for_selector(
                ".site-nav-user", timeout=120000, state="attached"
            )
            logger.info("检测到登录成功！正在保存状态...")
        except Exception:
            logger.warning("自动检测超时，尝试手动保存状态...")

        try:
            await context.storage_state(path=TAOBAO_STATE_FILE)
            logger.info(f"状态已保存到 {TAOBAO_STATE_FILE}")
        except Exception as e:
            logger.error(f"保存状态失败: {e}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(login_and_save_state())
