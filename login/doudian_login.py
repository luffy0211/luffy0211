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
logger = logging.getLogger("doudian_login")


async def login_and_save_state():
    """抖店商家后台扫码登录并保存状态"""
    
    state_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "state")
    os.makedirs(state_dir, exist_ok=True)
    state_file = os.path.join(state_dir, "doudian_state.json")
    
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
        
        logger.info("打开抖店商家后台...")
        await page.goto("https://fxg.jinritemai.com/index.html")
        
        logger.info("=" * 60)
        logger.info("请在浏览器中使用抖音APP扫码登录")
        logger.info("登录成功后，脚本会自动保存登录状态")
        logger.info("最长等待 120 秒...")
        logger.info("=" * 60)
        
        # 等待登录成功的标志
        try:
            # 抖店登录后会跳转到后台首页，检测后台特征元素
            await page.wait_for_selector(
                ".sidebar, .menu, [class*='avatar'], [class*='user'], [class*='shop-name'], [class*='header-right']",
                timeout=120000,
                state="attached"
            )
            logger.info("✓ 检测到登录成功！")
        except Exception as e:
            logger.warning(f"自动检测超时: {e}")
            logger.info("尝试保存当前状态...")
        
        # 额外等待确保页面完全加载
        await asyncio.sleep(3)
        
        # 保存登录状态
        try:
            await context.storage_state(path=state_file)
            logger.info(f"✓ 登录状态已保存到: {state_file}")
            logger.info("\n现在可以运行上架脚本了：")
            logger.info("  python main.py upload-doudian")
        except Exception as e:
            logger.error(f"保存状态失败: {e}")
        
        await asyncio.sleep(3)
        await browser.close()


async def login_interactive(page, context, state_file: str):
    """交互式登录（供 uploader 在状态失效时调用）
    
    Args:
        page: 当前页面（已在登录页）
        context: 浏览器上下文
        state_file: 状态文件保存路径
    
    Returns:
        bool: 登录是否成功
    """
    logger.info("=" * 60)
    logger.info("登录状态已失效，请在浏览器中扫码重新登录")
    logger.info("最长等待 120 秒...")
    logger.info("=" * 60)
    
    try:
        await page.wait_for_selector(
            ".sidebar, .menu, [class*='avatar'], [class*='user'], [class*='shop-name'], [class*='header-right']",
            timeout=12000000,
            state="attached"
        )
        logger.info("✓ 重新登录成功！")
        
        await asyncio.sleep(3)
        await context.storage_state(path=state_file)
        logger.info(f"✓ 登录状态已更新: {state_file}")
        return True
    except Exception as e:
        logger.error(f"重新登录失败: {e}")
        return False


if __name__ == "__main__":
    print("\n抖店登录工具")
    print("=" * 60)
    asyncio.run(login_and_save_state())
