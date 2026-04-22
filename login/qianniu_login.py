import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.async_api import async_playwright

import logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("qianniu_login")


async def login_and_save_state():
    state_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "state")
    os.makedirs(state_dir, exist_ok=True)
    state_file = os.path.join(state_dir, "qianniu_state.json")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            channel="msedge",
            args=["--start-maximized"]
        )
        
        context = await browser.new_context(
            no_viewport=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )
        
        page = await context.new_page()
        
        logger.info("打开千牛工作台登录页...")
        await page.goto("https://loginmyseller.taobao.com/")
        
        logger.info("请在浏览器中使用淘宝APP扫码登录")
        logger.info("登录成功后，脚本会自动保存登录状态")
        logger.info("最长等待 120 秒...")
        
        try:
            await page.wait_for_selector(
                ".sidebar, .menu, [class*='avatar'], [class*='user'], .tbh5-header, .seller-header",
                timeout=120000,
                state="attached"
            )
            logger.info("检测到登录成功！")
        except Exception as e:
            logger.warning(f"自动检测超时: {e}")
        
        await asyncio.sleep(3)
        
        try:
            await context.storage_state(path=state_file)
            logger.info(f"登录状态已保存到: {state_file}")
        except Exception as e:
            logger.error(f"保存状态失败: {e}")
        
        await asyncio.sleep(3)
        await browser.close()


async def login_interactive(page, context, state_file: str):
    logger.info("登录状态已失效，请在浏览器中扫码重新登录")
    
    try:
        await page.wait_for_selector(
            ".sidebar, .menu, [class*='avatar'], [class*='user'], .tbh5-header, .seller-header",
            timeout=120000,
            state="attached"
        )
        logger.info("重新登录成功！")
        
        await asyncio.sleep(3)
        await context.storage_state(path=state_file)
        logger.info(f"登录状态已更新: {state_file}")
        return True
    except Exception as e:
        logger.error(f"重新登录失败: {e}")
        return False


if __name__ == "__main__":
    print("\n千牛登录工具")
    asyncio.run(login_and_save_state())