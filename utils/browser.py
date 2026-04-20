import asyncio
from typing import Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from utils.logger import setup_logger

logger = setup_logger("browser")

STEALTH_INIT_SCRIPT = """
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
    Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) => (
        parameters.name === 'notifications'
            ? Promise.resolve({ state: Notification.permission })
            : originalQuery(parameters)
    );
    if (window.chrome) {
        window.chrome.runtime = { connect: function(){}, sendMessage: function(){} };
    }
"""

POPUP_JS = """
() => {
    const findAndClick = (root) => {
        const btns = root.querySelectorAll('button, .weui-desktop-btn, .weui-btn');
        for (const btn of btns) {
            const text = btn.innerText || '';
            if (text.includes('我知道了') || text.includes('确定') || text.includes('知道了')) {
                btn.click();
                return true;
            }
        }
        return false;
    };
    let found = findAndClick(document);
    const microApp = document.querySelector('micro-app[name="goods"]');
    if (microApp && microApp.shadowRoot) {
        if (findAndClick(microApp.shadowRoot)) found = true;
    }
    const microAppGeneric = document.querySelector('micro-app');
    if (microAppGeneric && microAppGeneric.shadowRoot && microAppGeneric !== microApp) {
        if (findAndClick(microAppGeneric.shadowRoot)) found = true;
    }
    return found;
}
"""


async def launch_browser(
    playwright,
    channel: str = "msedge",
    args: Optional[list] = None,
    headless: bool = False,
) -> Browser:
    default_args = [
        "--start-maximized",
        "--disable-blink-features=AutomationControlled",
        "--disable-dev-shm-usage",
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-infobars",
        "--window-size=1920,1080",
    ]
    browser = await playwright.chromium.launch(
        headless=headless,
        channel=channel,
        args=args or default_args,
    )
    logger.info(f"浏览器已启动 (channel={channel})")
    return browser


async def create_context(
    browser: Browser,
    state_file: Optional[str] = None,
    stealth: bool = False,
    no_viewport: bool = False,
) -> BrowserContext:
    kwargs = {}
    if state_file:
        kwargs["storage_state"] = state_file
    if no_viewport:
        kwargs["no_viewport"] = True
    else:
        kwargs["viewport"] = {"width": 1920, "height": 1080}
        kwargs["locale"] = "zh-CN"
        kwargs["timezone_id"] = "Asia/Shanghai"
        kwargs["extra_http_headers"] = {"Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"}

    context = await browser.new_context(**kwargs)

    if stealth:
        page_tmp = await context.new_page()
        await page_tmp.add_init_script(STEALTH_INIT_SCRIPT)
        await page_tmp.close()
        # apply init script to all future pages
        await context.add_init_script(STEALTH_INIT_SCRIPT)

    logger.info("浏览器上下文已创建")
    return context


async def apply_stealth(page: Page):
    try:
        from playwright_stealth import Stealth
        stealth = Stealth(
            navigator_webdriver=False,
            chrome_app=False,
            chrome_csi=False,
            chrome_load_times=False,
        )
        await stealth.apply_stealth_async(page)
        logger.info("Stealth 反检测已应用")
    except ImportError:
        await page.add_init_script(STEALTH_INIT_SCRIPT)
        logger.warning("playwright-stealth 未安装，使用内置反检测脚本")


async def handle_popups(page: Page, max_attempts: int = 3):
    logger.info("正在扫描并清理弹窗...")
    for i in range(max_attempts):
        try:
            if await page.evaluate(POPUP_JS):
                logger.info(f"成功关闭弹窗 (第{i+1}次)")
                await asyncio.sleep(1)
            else:
                break
        except Exception as e:
            logger.warning(f"弹窗处理异常: {e}")
            break


async def check_login_state(page: Page, check_url: str, success_indicator: str, timeout: int = 10000) -> bool:
    try:
        await page.goto(check_url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_selector(success_indicator, timeout=timeout)
        logger.info("登录状态有效")
        return True
    except Exception:
        logger.warning("登录状态已过期或无效")
        return False
