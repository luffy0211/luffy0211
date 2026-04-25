import asyncio
import json
import os
import re
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.async_api import async_playwright, Locator, Page

from config import BROWSER_CHANNEL, DESKTOP_PATH, DOUDIAN_UPLOAD_COLUMNS, DOUDIAN_UPLOAD_EXCEL
from utils.browser import create_context, handle_popups, launch_browser
from utils.excel import read_upload_data
from utils.image import get_images_from_folder
from utils.logger import setup_logger

STATE_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "state",
    "qianniu_state.json",
)
QIANNIU_GOODS_URL = "https://item.upload.taobao.com/sell/ai/category.htm"
QIANNIU_UPLOAD_EXCEL = DOUDIAN_UPLOAD_EXCEL
QIANNIU_UPLOAD_COLUMNS = DOUDIAN_UPLOAD_COLUMNS
DEFAULT_STOCK = 10
ACTION_RETRY_COUNT = 3
ACTION_RETRY_DELAY_MS = 600
POST_ACTION_DELAY_MS = 300
PAGE_SETTLE_TIMEOUT_MS = 10000
UPLOAD_READY_TIMEOUT_MS = 30000
ITEM_MAX_RETRIES = 2

CATEGORY_UPLOAD_TRIGGER_SELECTORS = [
    'xpath=//*[@id="ai-category-page-main-do-not-add-padding"]//button[.//span]',
    'xpath=//*[@id="ai-category-page-main-do-not-add-padding"]/div/div[4]/div/div/div/div/div[2]/div/div/div/div/div/button/span',
]
CATEGORY_CONFIRM_SELECTORS = [
    'xpath=//*[@id="ai-category-page-main-do-not-add-padding"]/div/div[4]/div[2]/div/div[2]/button',
    'xpath=//*[@id="ai-category-page-main-do-not-add-padding"]/div/div[4]/div[2]/div/div[2]/button/span[1]',
]
BRAND_INPUT_SELECTORS = [
    'xpath=//*[@id="struct-p-20000"]/span/span[1]/span[1]/span/input',
    'xpath=//div[@id="struct-p-20000"]//input',
]
BRAND_OPTION_SELECTORS = [
    'xpath=/html/body/div[6]/div/div/div[2]/div/div/div/div[1]',
    'xpath=//div[contains(@class,"next-overlay-wrapper")]//*[normalize-space()="无品牌"]',
    'xpath=(//div[contains(@class,"next-overlay-wrapper")]//div[@role="option"])[1]',
]
NEXT_STEP_SELECTORS = [
    'xpath=//div[contains(@class,"ai-category-image-mode-footer")]//button[span[text()="确认，下一步"]]',
    'xpath=//button[span[text()="确认，下一步"]]',
]
TITLE_INPUT_SELECTORS = [
    'xpath=//span[@title="宝贝标题"]/ancestor::div[contains(@class,"sell-component-info-wrapper")]//input',
    'xpath=//input[@placeholder="请输入宝贝标题"]',
]
COLOR_INPUT_SELECTOR = 'xpath=//div[contains(@id,"struct-p-")]//input[@placeholder="主色(必选)"]'
ADD_INPUT_SELECTOR = 'xpath=(//i[@class="next-icon next-icon-add next-xs next-btn-icon next-icon-alone"])[1]'
OVERLAY_INPUT_SELECTORS = [
    'xpath=(/html/body/div[last()]//input)[last()]',
    'xpath=(//div[contains(@class,"next-overlay-wrapper")]//input)[last()]',
    'xpath=(//div[contains(@class,"next-select-inner")]//input)[last()]',
]
NO_DATA_SELECTORS = [
    'xpath=//div[contains(@class,"next-overlay-wrapper")]//*[normalize-space()="暂无数据"]',
    'xpath=//div[contains(@class,"next-overlay-wrapper")]//*[contains(normalize-space(),"暂无")]',
]
BATCH_FILL_BUTTON_SELECTORS = [
    'button:has-text("批量填写")',
    'xpath=//button[normalize-space()="批量填写"]',
]
BATCH_SALE_PRICE_SELECTORS = [
    'xpath=//*[@id="sku-batch-setting"]/div[2]/div[2]/div/div/div[1]/input',
    'xpath=(//div[@id="sku-batch-setting"]//input)[1]',
]
BATCH_STOCK_SELECTORS = [
    'xpath=//*[@id="sku-batch-setting"]/div[2]/div[3]/div/div/div[1]/input',
    'xpath=(//div[@id="sku-batch-setting"]//input)[2]',
]
BATCH_MARKET_PRICE_SELECTORS = [
    'xpath=//*[@id="sku-batch-setting"]/div[2]/div[4]/div/div/div[1]/input',
    'xpath=(//div[@id="sku-batch-setting"]//input)[3]',
]
BATCH_CONFIRM_SELECTORS = [
    '.d-drawer-footer button:has-text("确定")',
    'button:has-text("确定")',
    'xpath=//button[contains(normalize-space(),"确定")]',
]
SUBMIT_BUTTON_SELECTORS = [
    'xpath=//div[contains(@class,"action-bar")]//button[normalize-space()="提交商品"]',
    'xpath=//button[normalize-space()="提交商品"]',
    'xpath=//button[normalize-space()="发布商品"]',
]

ATTRIBUTE_ALIASES = {
    "style": ["风格"],
    "season": ["适用季节", "季节"],
    "fabric": ["面料", "面料材质"],
    "material_composition": ["材质成分", "材质"],
    "safety_level": ["安全等级"],
}

logger = setup_logger("qianniu_uploader")


def stringify_value(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def split_multi_values(value) -> list[str]:
    text = stringify_value(value)
    if not text:
        return []
    normalized = re.sub(r"[,，;；]+", " ", text)
    return [part.strip() for part in normalized.split() if part.strip()]


def extract_primary_material(value) -> str:
    for part in split_multi_values(value):
        cleaned = re.sub(r"[\d%()（）]+", "", part).strip()
        if cleaned:
            return cleaned
    return ""


def format_market_price(value) -> str:
    text = stringify_value(value)
    if not text:
        return ""
    try:
        market_price = round(float(text) * 3, 2)
        if market_price.is_integer():
            return str(int(market_price))
        return f"{market_price:.2f}".rstrip("0").rstrip(".")
    except Exception:
        return text


def xpath_literal(value: str) -> str:
    if '"' not in value:
        return f'"{value}"'
    if "'" not in value:
        return f"'{value}'"
    parts = value.split('"')
    pieces = []
    for index, part in enumerate(parts):
        if part:
            pieces.append(f'"{part}"')
        if index != len(parts) - 1:
            pieces.append("'\"'")
    return "concat(" + ", ".join(pieces) + ")"


async def is_page_closed(page: Page) -> bool:
    try:
        return page.is_closed()
    except Exception:
        return True


async def wait_ms(ms: int):
    await asyncio.sleep(ms / 1000)


async def wait_for_page_settle(
    page: Page,
    description: str = "页面",
    timeout: int = PAGE_SETTLE_TIMEOUT_MS,
):
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=timeout)
    except Exception:
        logger.debug(f"{description} 未能在预期时间内完成 domcontentloaded")

    try:
        await page.wait_for_load_state("networkidle", timeout=min(timeout, 5000))
    except Exception:
        logger.debug(f"{description} 未进入 networkidle，继续执行")

    await wait_ms(POST_ACTION_DELAY_MS)


async def wait_for_any_visible(
    page: Page,
    selector_groups: list[list[str]],
    description: str,
    timeout: int,
) -> bool:
    deadline = asyncio.get_running_loop().time() + timeout / 1000
    while asyncio.get_running_loop().time() < deadline:
        for selectors in selector_groups:
            locator = await get_first_visible_locator(page, selectors, timeout=700)
            if locator is not None:
                logger.info(f"{description}已就绪")
                return True
        await wait_ms(ACTION_RETRY_DELAY_MS)

    logger.warning(f"{description}等待超时")
    return False


async def read_input_value(locator: Locator) -> str:
    try:
        return await locator.input_value()
    except Exception:
        pass

    try:
        return (await locator.get_attribute("value")) or ""
    except Exception:
        return ""


async def get_first_visible_locator(
    page: Page,
    selectors: list[str],
    timeout: int = 3000,
) -> Locator | None:
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            await locator.wait_for(state="visible", timeout=timeout)
            return locator
        except Exception:
            continue
    return None


async def click_locator(locator: Locator, description: str, *, force: bool = False):
    last_exc = None
    for attempt in range(1, ACTION_RETRY_COUNT + 1):
        try:
            await locator.wait_for(state="visible", timeout=3000)
            try:
                await locator.scroll_into_view_if_needed()
            except Exception:
                pass

            await locator.click(force=force, timeout=5000)
            await wait_ms(POST_ACTION_DELAY_MS)
            logger.info(f"已点击{description}")
            return
        except Exception as exc:
            last_exc = exc
            logger.warning(f"点击{description}失败，第 {attempt} 次重试: {exc}")
            await wait_ms(ACTION_RETRY_DELAY_MS * attempt)

    raise last_exc or RuntimeError(f"点击{description}失败")


async def click_first_visible(
    page: Page,
    selectors: list[str],
    description: str,
    timeout: int = 3000,
    *,
    force: bool = False,
) -> bool:
    locator = await get_first_visible_locator(page, selectors, timeout=timeout)
    if locator is None:
        logger.warning(f"未找到{description}")
        return False

    try:
        await click_locator(locator, description, force=force)
        return True
    except Exception as exc:
        logger.warning(f"{description}点击失败: {exc}")
        return False


async def clear_and_fill(locator: Locator, value: str):
    last_exc = None
    for attempt in range(1, ACTION_RETRY_COUNT + 1):
        try:
            await locator.wait_for(state="visible", timeout=3000)
            await locator.click(force=True, timeout=5000)
            await wait_ms(POST_ACTION_DELAY_MS)
            try:
                await locator.press("Control+A")
                await locator.press("Backspace")
            except Exception:
                pass

            try:
                await locator.fill(value)
            except Exception:
                await locator.type(value, delay=50)

            current_value = (await read_input_value(locator)).strip()
            if value and current_value and current_value != value.strip():
                raise ValueError(f"输入值校验失败，当前值为: {current_value}")

            await wait_ms(POST_ACTION_DELAY_MS)
            return
        except Exception as exc:
            last_exc = exc
            logger.warning(f"填写输入框失败，第 {attempt} 次重试: {exc}")
            await wait_ms(ACTION_RETRY_DELAY_MS * attempt)

    raise last_exc or RuntimeError("填写输入框失败")


async def overlay_has_no_data(page: Page) -> bool:
    return await get_first_visible_locator(page, NO_DATA_SELECTORS, timeout=800) is not None


async def choose_overlay_option(page: Page, value: str, *, allow_first: bool = False) -> bool:
    literal = xpath_literal(value)
    selectors = [
        f'xpath=(//div[contains(@class,"next-overlay-wrapper")]//*[normalize-space()={literal}])[1]',
        f'xpath=(//div[contains(@class,"next-overlay-wrapper")]//*[contains(normalize-space(), {literal})])[1]',
        f'xpath=(//li[contains(@class,"next-menu-item")]//*[normalize-space()={literal}])[1]',
    ]

    if allow_first:
        selectors.extend(
            [
                'xpath=(//div[contains(@class,"next-overlay-wrapper")]//div[@role="option"])[1]',
                'xpath=(//li[contains(@class,"next-menu-item")])[1]',
            ]
        )

    locator = await get_first_visible_locator(page, selectors, timeout=2000)
    if locator is None:
        return False

    await click_locator(locator, f"下拉项 {value}")
    return True


async def fill_text_input_and_select(
    page: Page,
    input_locator: Locator,
    value: str,
    description: str,
    *,
    fallback: str | None = "其他",
) -> bool:
    text = stringify_value(value)
    if not text:
        return False

    await clear_and_fill(input_locator, text)
    await page.wait_for_timeout(800)

    if await choose_overlay_option(page, text):
        logger.info(f"已填写{description}: {text}")
        return True

    if fallback and await overlay_has_no_data(page):
        await clear_and_fill(input_locator, fallback)
        await page.wait_for_timeout(600)
        if await choose_overlay_option(page, fallback, allow_first=True):
            logger.info(f"{description} 无匹配项，已回退为: {fallback}")
            return True

    try:
        await input_locator.press("Enter")
    except Exception:
        await page.keyboard.press("Enter")

    logger.info(f"已填写{description}: {text}")
    return True


async def fill_trigger_field_and_select(
    page: Page,
    trigger_locator: Locator,
    value: str,
    description: str,
    *,
    fallback: str | None = "其他",
) -> bool:
    text = stringify_value(value)
    if not text:
        return False

    await click_locator(trigger_locator, description)
    await page.wait_for_timeout(300)

    input_locator = await get_first_visible_locator(page, OVERLAY_INPUT_SELECTORS, timeout=1500)
    if input_locator is not None:
        await clear_and_fill(input_locator, text)
    else:
        await page.keyboard.type(text, delay=50)

    await page.wait_for_timeout(800)

    if await choose_overlay_option(page, text):
        logger.info(f"已填写{description}: {text}")
        return True

    if fallback and await overlay_has_no_data(page):
        if input_locator is not None:
            await clear_and_fill(input_locator, fallback)
        else:
            await page.keyboard.press("Control+A")
            await page.keyboard.press("Backspace")
            await page.keyboard.type(fallback, delay=50)
        await page.wait_for_timeout(600)
        if await choose_overlay_option(page, fallback, allow_first=True):
            logger.info(f"{description} 无匹配项，已回退为: {fallback}")
            return True

    await page.keyboard.press("Enter")
    logger.info(f"已填写{description}: {text}")
    return True


async def check_and_relogin(page: Page, context) -> bool:
    try:
        current_url = page.url.lower()
        if "login" not in current_url and "passport" not in current_url:
            return True

        logger.warning("检测到登录页，尝试重新登录")
        from login.qianniu_login import login_interactive

        return await login_interactive(page, context, STATE_FILE)
    except Exception as exc:
        logger.error(f"登录状态检查失败: {exc}")
        return False


async def upload_category_images(page: Page, image_files: list[str]) -> bool:
    if await is_page_closed(page):
        return False
    if not image_files:
        logger.warning("无可上传图片")
        return False

    trigger = await get_first_visible_locator(page, CATEGORY_UPLOAD_TRIGGER_SELECTORS, timeout=10000)
    if trigger is None:
        logger.error("未找到分类页上传按钮")
        return False

    try:
        async with page.expect_file_chooser(timeout=5000) as chooser_info:
            await click_locator(trigger, "分类页上传按钮")
        chooser = await chooser_info.value
        await chooser.set_files(image_files)
    except Exception:
        logger.warning("文件选择器未捕获，尝试直接写入 file input")
        try:
            await click_locator(trigger, "分类页上传按钮", force=True)
        except Exception:
            pass
        file_inputs = page.locator('input[type="file"]')
        input_count = await file_inputs.count()
        if input_count == 0:
            logger.error("未找到 file input，无法上传图片")
            return False
        await file_inputs.nth(input_count - 1).set_input_files(image_files)

    logger.info(f"分类页已选择 {len(image_files)} 张图片")
    await page.wait_for_timeout(3000)
    return True


async def confirm_category_selection(page: Page) -> bool:
    if not await click_first_visible(page, CATEGORY_CONFIRM_SELECTORS, "分类确认按钮", timeout=8000):
        return False

    await page.wait_for_timeout(2000)
    return True


async def select_no_brand(page: Page) -> bool:
    brand_input = await get_first_visible_locator(page, BRAND_INPUT_SELECTORS, timeout=12000)
    if brand_input is None:
        logger.warning("未找到品牌输入框")
        return False

    await clear_and_fill(brand_input, "无品牌")
    await page.wait_for_timeout(1000)

    if await click_first_visible(page, BRAND_OPTION_SELECTORS, "无品牌选项", timeout=3000):
        logger.info("已选择品牌: 无品牌")
        return True

    try:
        await brand_input.press("Enter")
        logger.info("已回车确认品牌: 无品牌")
        return True
    except Exception as exc:
        logger.warning(f"选择无品牌失败: {exc}")
        return False


async def fill_title_manual(page: Page, title: str) -> bool:
    title_input = await get_first_visible_locator(page, TITLE_INPUT_SELECTORS, timeout=12000)
    if title_input is None:
        logger.warning("未找到宝贝标题输入框")
        return False

    await clear_and_fill(title_input, stringify_value(title))
    logger.info(f"已填写宝贝标题: {title}")
    return True


async def fill_colors(page: Page, colors: list[str]) -> bool:
    if not colors:
        return True

    logger.info(f"准备填写 {len(colors)} 个颜色分类: {colors}")

    for index, color in enumerate(colors):
        color_inputs = page.locator(COLOR_INPUT_SELECTOR)
        if index > 0 and await color_inputs.count() <= index:
            if not await click_first_visible(page, [ADD_INPUT_SELECTOR], "颜色添加按钮", timeout=3000):
                logger.warning(f"无法新增第 {index + 1} 个颜色输入框")
                continue
            await page.wait_for_timeout(500)
            color_inputs = page.locator(COLOR_INPUT_SELECTOR)

        if await color_inputs.count() <= index:
            logger.warning(f"未找到第 {index + 1} 个颜色输入框")
            continue

        await fill_text_input_and_select(
            page,
            color_inputs.nth(index),
            color,
            f"颜色分类 {index + 1}",
            fallback=None,
        )
        await page.wait_for_timeout(500)

    return True


async def find_attribute_field(page: Page, aliases: list[str]) -> tuple[Locator | None, str | None]:
    for alias in aliases:
        literal = xpath_literal(alias)
        input_selector = (
            'xpath=(//div[contains(@id,"sell-field-p-") and .//span[@title=' + literal + ']]//input)[1]'
        )
        trigger_selector = (
            'xpath=(//div[contains(@id,"sell-field-p-") and .//span[@title=' + literal + ']]//span[contains(@class,"next-select-trigger")])[1]'
        )

        input_locator = page.locator(input_selector).first
        try:
            await input_locator.wait_for(state="visible", timeout=1000)
            return input_locator, "input"
        except Exception:
            pass

        trigger_locator = page.locator(trigger_selector).first
        try:
            await trigger_locator.wait_for(state="visible", timeout=1000)
            return trigger_locator, "trigger"
        except Exception:
            pass

    return None, None


async def fill_single_attribute(page: Page, attr_name: str, value: str) -> bool:
    aliases = ATTRIBUTE_ALIASES.get(attr_name, [attr_name])
    field, mode = await find_attribute_field(page, aliases)
    if field is None or mode is None:
        logger.warning(f"未找到属性字段: {aliases[0]}")
        return False

    text = stringify_value(value)
    if not text:
        return False

    if mode == "input":
        return await fill_text_input_and_select(page, field, text, aliases[0])
    return await fill_trigger_field_and_select(page, field, text, aliases[0])


async def fill_product_attributes(page: Page, item: dict) -> bool:
    attribute_values = {
        "style": item.get("style"),
        "season": item.get("season"),
        "fabric": item.get("fabric") or item.get("material"),
        "material_composition": extract_primary_material(item.get("material_composition") or item.get("material")),
        "safety_level": item.get("safety_level"),
    }

    for attr_name, value in attribute_values.items():
        text = stringify_value(value)
        if not text:
            continue
        await fill_single_attribute(page, attr_name, text)
        await page.wait_for_timeout(500)

    return True


async def batch_fill_price_stock(
    page: Page,
    sale_price: str,
    market_price: str,
    stock: int = DEFAULT_STOCK,
) -> bool:
    batch_button = await get_first_visible_locator(page, BATCH_FILL_BUTTON_SELECTORS, timeout=5000)
    if batch_button is None:
        logger.warning("未找到批量填写按钮，跳过价格库存")
        return False

    await click_locator(batch_button, "批量填写按钮")
    await page.wait_for_timeout(1000)

    sale_input = await get_first_visible_locator(page, BATCH_SALE_PRICE_SELECTORS, timeout=3000)
    if sale_input is not None:
        await clear_and_fill(sale_input, sale_price)
        logger.info(f"已填写售价: {sale_price}")

    stock_input = await get_first_visible_locator(page, BATCH_STOCK_SELECTORS, timeout=3000)
    if stock_input is not None:
        await clear_and_fill(stock_input, stringify_value(stock))
        logger.info(f"已填写库存: {stock}")

    market_input = await get_first_visible_locator(page, BATCH_MARKET_PRICE_SELECTORS, timeout=3000)
    if market_input is not None and market_price:
        await clear_and_fill(market_input, market_price)
        logger.info(f"已填写市场价: {market_price}")

    if not await click_first_visible(page, BATCH_CONFIRM_SELECTORS, "批量填写确认按钮", timeout=3000):
        await page.keyboard.press("Enter")
        logger.info("未找到批量填写确认按钮，已尝试回车确认")

    await page.wait_for_timeout(1000)
    return True


async def submit_product(page: Page) -> bool:
    if not await click_first_visible(page, SUBMIT_BUTTON_SELECTORS, "提交商品按钮", timeout=5000):
        return False

    await page.wait_for_timeout(3000)
    return True


async def process_single_item(page: Page, item: dict, index: int):
    logger.info(f"\n{'=' * 60}")
    logger.info(f"--- 正在处理第 {index} 条商品 ---")

    if await is_page_closed(page):
        return False

    image_files = get_images_from_folder(stringify_value(item.get("image_path")))
    if not image_files:
        logger.warning("无主图可用于千牛识别上传")
        return False

    title = stringify_value(item.get("title"))
    colors = split_multi_values(item.get("color"))
    sale_price = stringify_value(item.get("sale_price") or item.get("price"))
    market_price = format_market_price(item.get("price") or item.get("sale_price"))

    await handle_popups(page)

    if not await upload_category_images(page, image_files):
        return False

    if not await confirm_category_selection(page):
        return False

    await select_no_brand(page)

    if not await click_first_visible(page, NEXT_STEP_SELECTORS, "确认下一步按钮", timeout=10000):
        return False

    await page.wait_for_timeout(4000)
    await handle_popups(page)

    if title:
        await fill_title_manual(page, title)

    await fill_product_attributes(page, item)

    if colors:
        await fill_colors(page, colors)

    if sale_price:
        await batch_fill_price_stock(page, sale_price, market_price, DEFAULT_STOCK)

    await submit_product(page)
    logger.info(f"第 {index} 条商品处理完成")
    return True


async def run_uploader():
    if not os.path.exists(STATE_FILE):
        logger.error(f"未找到登录状态文件: {STATE_FILE}")
        logger.error("请先执行千牛登录")
        return

    data = read_upload_data(QIANNIU_UPLOAD_EXCEL, QIANNIU_UPLOAD_COLUMNS)
    if not data:
        logger.error("无可用上架数据，请检查 Excel 文件")
        return

    logger.info(f"共 {len(data)} 条商品待上架到千牛")
    results = []

    async with async_playwright() as p:
        browser = await launch_browser(p, channel=BROWSER_CHANNEL)
        context = await create_context(browser, state_file=STATE_FILE, no_viewport=True)
        page = await context.new_page()

        try:
            for index, item in enumerate(data, 1):
                success = False
                try:
                    await page.goto(QIANNIU_GOODS_URL, wait_until="domcontentloaded")
                    await asyncio.sleep(3)

                    if not await check_and_relogin(page, context):
                        logger.error("登录失效且重新登录失败，终止上架")
                        break

                    await handle_popups(page)
                    success = await process_single_item(page, item, index)
                except Exception as exc:
                    logger.error(f"处理第 {index} 条商品失败: {exc}")
                finally:
                    results.append(
                        {
                            "index": index,
                            "title": stringify_value(item.get("title")),
                            "success": bool(success),
                        }
                    )

                if index < len(data):
                    await page.wait_for_timeout(2000)

            success_count = sum(1 for result in results if result["success"])
            failed_count = len(results) - success_count
            logger.info(
                f"\n全部完成，共处理 {len(results)} 条，成功 {success_count}，失败 {failed_count}"
            )

            result_file = os.path.join(
                DESKTOP_PATH,
                f"qianniu_upload_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            )
            with open(result_file, "w", encoding="utf-8") as file:
                json.dump(
                    {
                        "total": len(results),
                        "success": success_count,
                        "failed": failed_count,
                        "results": results,
                    },
                    file,
                    ensure_ascii=False,
                    indent=2,
                )
            logger.info(f"结果已保存到: {result_file}")
        finally:
            await browser.close()
            logger.info("浏览器已关闭")


if __name__ == "__main__":
    asyncio.run(run_uploader())



