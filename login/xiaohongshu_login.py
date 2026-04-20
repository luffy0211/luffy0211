import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.async_api import async_playwright

# 简化版logger
import logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("xhs_login")


async def login_xiaohongshu():
    """小红书商家后台登录并保存状态"""
    
    state_dir = "state"
    os.makedirs(state_dir, exist_ok=True)
    state_file = os.path.join(state_dir, "xiaohongshu_state.json")
    
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
        
        logger.info("打开小红书商家后台...")
        await page.goto("https://ark.xiaohongshu.com/")

        
        logger.info("=" * 60)
        logger.info("请在浏览器中完成登录（扫码或账号密码）")
        logger.info("登录成功后，浏览器会自动保存登录状态")
        logger.info("等待 120 秒...")
        logger.info("=" * 60)
        
        # 等待登录成功的标志
        try:
            # 等待登录后的页面元素（根据实际页面调整）
            await page.wait_for_selector(
                ".user-info, .avatar, [class*='user'], [class*='header']",
                timeout=12000000,
                state="attached"
            )
            logger.info("✓ 检测到登录成功！")
        except Exception as e:
            logger.warning(f"自动检测超时: {e}")
            logger.info("尝试保存当前状态...")
        
        # 保存登录状态
        try:
            await context.storage_state(path=state_file)
            logger.info(f"✓ 登录状态已保存到: {state_file}")
            logger.info("\n现在可以运行上架脚本了：")
            logger.info("  python run_xhs_upload.py")
        except Exception as e:
            logger.error(f"保存状态失败: {e}")
        
        await asyncio.sleep(3)
        await browser.close()


if __name__ == "__main__":
    print("\n小红书登录工具")
    print("=" * 60)
    asyncio.run(login_xiaohongshu())
