import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.async_api import async_playwright
from utils.browser import launch_browser, create_context, handle_popups
from utils.excel import read_upload_data
from utils.image import get_images_from_folder
from utils.logger import setup_logger
from config import (
    SHIPINHAO_STATE_FILE, BROWSER_CHANNEL,
    SHIPINHAO_UPLOAD_EXCEL, UPLOAD_COLUMNS,
    SHIPINHAO_GOODS_URL, SHIPINHAO_MICRO_APP,
)

logger = setup_logger("shipinhao_uploader")


def _shadow_js(script: str) -> str:
    """包装 JS 代码以访问微应用 Shadow DOM"""
    return f"""
    () => {{
        const microApp = document.querySelector('micro-app[name="goods"]');
        if (!microApp || !microApp.shadowRoot) return {{ success: false, reason: 'no shadow root' }};
        const shadowRoot = microApp.shadowRoot;
        {script}
    }}
    """


def _shadow_js_with_arg(script: str) -> str:
    """包装带参数的 JS 代码"""
    return f"""
    (arg) => {{
        const microApp = document.querySelector('micro-app[name="goods"]');
        if (!microApp || !microApp.shadowRoot) return {{ success: false, reason: 'no shadow root' }};
        const shadowRoot = microApp.shadowRoot;
        {script}
    }}
    """


async def upload_images(page, image_files: list[str]):
    """上传商品图片"""
    logger.info(f"准备上传 {len(image_files)} 张图片...")
    await page.wait_for_timeout(3000)

    try:
        async with page.expect_file_chooser(timeout=15000) as fc_info:
            await page.evaluate(_shadow_js("""
                const selectors = [
                    '.picture_add_content', '.icon_add',
                    '.goods-image-upload', '[class*="upload"]',
                    '[class*="picture"]', '[class*="add"]'
                ];
                for (const sel of selectors) {
                    const elements = shadowRoot.querySelectorAll(sel);
                    for (const el of elements) {
                        if (el.offsetWidth > 0 && el.offsetHeight > 0) {
                            el.click();
                            return { success: true };
                        }
                    }
                }
                return { success: false, reason: 'no upload area found' };
            """))

        file_chooser = await fc_info.value
        await file_chooser.set_files(image_files)
        logger.info("图片上传指令已发送")
        await page.wait_for_timeout(5000)
    except Exception as e:
        logger.error(f"图片上传失败: {e}")


async def fill_title(page, title: str):
    """填写商品标题"""
    try:
        result = await page.evaluate(_shadow_js_with_arg("""
            const selectors = [
                'input[placeholder*="商品名称"]',
                'input[placeholder*="关键字"]',
                'input[placeholder*="商品标题"]',
                'input[placeholder*="标题"]',
                'input[data-eleid="product_title"]',
                '.weui-desktop-form__input'
            ];
            for (const sel of selectors) {
                const input = shadowRoot.querySelector(sel);
                if (input) {
                    input.value = arg;
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                    input.dispatchEvent(new Event('change', { bubbles: true }));
                    return { success: true, selector: sel };
                }
            }
            return { success: false, reason: 'title input not found' };
        """), title)

        if result.get("success"):
            logger.info(f"标题已填写: {title}")
        else:
            logger.warning(f"标题填写失败: {result.get('reason')}")
    except Exception as e:
        logger.error(f"标题填写异常: {e}")


async def click_next_button(page):
    """点击下一步按钮"""
    await page.wait_for_timeout(2000)

    try:
        for attempt in range(30):
            result = await page.evaluate(_shadow_js("""
                const selectors = [
                    'button.weui-desktop-btn_primary',
                    '.button_content button',
                    '.weui-desktop-btn_wrp button',
                    '.fix_box button'
                ];
                for (const sel of selectors) {
                    const buttons = shadowRoot.querySelectorAll(sel);
                    for (const btn of buttons) {
                        const text = btn.textContent || btn.innerText || '';
                        if (text.includes('下一步') && !btn.className.includes('weui-desktop-btn_disabled')) {
                            btn.click();
                            return { success: true };
                        }
                    }
                }
                return { success: false, reason: 'button not ready' };
            """))

            if result.get("success"):
                logger.info("已点击下一步按钮")
                return
            await page.wait_for_timeout(500)

        logger.warning("下一步按钮未就绪")
    except Exception as e:
        logger.error(f"点击下一步失败: {e}")


async def fill_input_field(page, placeholder_keyword: str, value: str, field_name: str):
    """通用：在 Shadow DOM 中查找含指定 placeholder 的 input 并填值"""
    try:
        result = await page.evaluate(_shadow_js_with_arg(f"""
            const selectors = [
                'input[placeholder*="{placeholder_keyword}"]',
                '.main-option input[placeholder*="{placeholder_keyword}"]',
                '.weui-desktop-form__input'
            ];
            for (const sel of selectors) {{
                const inputs = shadowRoot.querySelectorAll(sel);
                for (const input of inputs) {{
                    const ph = input.placeholder || '';
                    if (ph.includes('{placeholder_keyword}')) {{
                        input.value = arg;
                        input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        return {{ success: true, selector: sel }};
                    }}
                }}
            }}
            return {{ success: false, reason: 'input not found' }};
        """), value)

        if result.get("success"):
            logger.info(f"{field_name}已填写: {value}")
        else:
            logger.warning(f"{field_name}填写失败: {result.get('reason')}")
    except Exception as e:
        logger.error(f"{field_name}填写异常: {e}")


async def select_style(page, style_text: str):
    """选择风格下拉框"""
    try:
        await page.evaluate(_shadow_js("""
            const dropdown = shadowRoot.querySelector('input[placeholder*="风格"]');
            if (dropdown) dropdown.click();
        """))

        await page.wait_for_timeout(800)

        result = await page.evaluate(_shadow_js_with_arg("""
            const options = shadowRoot.querySelectorAll('.weui-desktop-dropdown__list-ele');
            for (const opt of options) {
                const text = opt.textContent || opt.innerText || '';
                if (text.includes(arg)) {
                    opt.click();
                    return { success: true, selected: text.trim() };
                }
            }
            if (options.length > 0) {
                options[0].click();
                return { success: true, selected: 'first_option' };
            }
            return { success: false, reason: 'no options found' };
        """), style_text)

        if result.get("success"):
            logger.info(f"风格已选择: {result.get('selected', style_text)}")
        else:
            logger.warning(f"风格选择失败: {result.get('reason')}")
    except Exception as e:
        logger.error(f"风格选择异常: {e}")


async def fill_colors(page, colors: list[str]):
    """填写多个颜色（逗号分隔）"""
    if not colors:
        return
    
    logger.info(f"准备填写 {len(colors)} 个颜色: {colors}")
    
    for i, color in enumerate(colors):
        try:
            # 使用 XPath 定位颜色输入框
            result = await page.evaluate(_shadow_js_with_arg(f"""
                const xpath = "//div[contains(@class,'goods-attr-item')]//input[@placeholder='请输入颜色']";
                const inputs = shadowRoot.evaluate(xpath, shadowRoot, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
                
                if (inputs.snapshotLength > {i}) {{
                    const input = inputs.snapshotItem({i});
                    input.value = arg;
                    input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    return {{ success: true, index: {i} }};
                }}
                return {{ success: false, reason: 'color input not found at index {i}' }};
            """), color)
            
            if result.get("success"):
                logger.info(f"颜色 {i+1} 已填写: {color}")
            else:
                logger.warning(f"颜色 {i+1} 填写失败: {result.get('reason')}")
            
            await page.wait_for_timeout(500)
        except Exception as e:
            logger.error(f"颜色 {i+1} 填写异常: {e}")


async def fill_sizes(page, sizes: list[str]):
    """填写多个尺码（空格分隔）"""
    if not sizes:
        return
    
    logger.info(f"准备填写 {len(sizes)} 个尺码: {sizes}")
    
    for i, size in enumerate(sizes):
        try:
            # 使用 XPath 定位尺码输入框
            result = await page.evaluate(_shadow_js_with_arg(f"""
                const xpath = "//input[@placeholder='请输入尺码']";
                const inputs = shadowRoot.evaluate(xpath, shadowRoot, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
                
                if (inputs.snapshotLength > {i}) {{
                    const input = inputs.snapshotItem({i});
                    input.value = arg;
                    input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    return {{ success: true, index: {i} }};
                }}
                return {{ success: false, reason: 'size input not found at index {i}' }};
            """), size)
            
            if result.get("success"):
                logger.info(f"尺码 {i+1} 已填写: {size}")
            else:
                logger.warning(f"尺码 {i+1} 填写失败: {result.get('reason')}")
            
            await page.wait_for_timeout(500)
        except Exception as e:
            logger.error(f"尺码 {i+1} 填写异常: {e}")


async def fill_price(page, price: float):
    """填写售卖价"""
    if not price:
        return
    
    try:
        # 使用 XPath 定位售卖价输入框
        result = await page.evaluate(_shadow_js_with_arg("""
            const xpath = "(//span[normalize-space()='售卖价']/following::input[@placeholder='填写售卖价'])[1]";
            const input = shadowRoot.evaluate(xpath, shadowRoot, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
            
            if (input) {
                input.value = arg;
                input.dispatchEvent(new Event('input', { bubbles: true }));
                input.dispatchEvent(new Event('change', { bubbles: true }));
                return { success: true };
            }
            return { success: false, reason: 'price input not found' };
        """), str(price))
        
        if result.get("success"):
            logger.info(f"售卖价已填写: {price}")
        else:
            logger.warning(f"售卖价填写失败: {result.get('reason')}")
    except Exception as e:
        logger.error(f"售卖价填写异常: {e}")


async def fill_stock_default(page, stock: int = 10):
    """填写库存（默认10）"""
    try:
        # 使用 XPath 定位库存输入框
        result = await page.evaluate(_shadow_js_with_arg("""
            const xpath = "(//span[normalize-space()='库存']/following::input[@placeholder='输入库存'])[1]";
            const input = shadowRoot.evaluate(xpath, shadowRoot, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
            
            if (input) {
                input.value = arg;
                input.dispatchEvent(new Event('input', { bubbles: true }));
                input.dispatchEvent(new Event('change', { bubbles: true }));
                return { success: true };
            }
            return { success: false, reason: 'stock input not found' };
        """), str(stock))
        
        if result.get("success"):
            logger.info(f"库存已填写: {stock}")
        else:
            logger.warning(f"库存填写失败: {result.get('reason')}")
    except Exception as e:
        logger.error(f"库存填写异常: {e}")


async def process_single_item(page, item: dict, index: int):
    """处理单个商品上架"""
    logger.info(f"\n--- 正在处理第 {index} 条 ---")
    image_path = item.get("image_path")
    title = item.get("title")
    material = item.get("material")
    color = item.get("color")
    style = item.get("style")
    price = item.get("price")
    sizes = item.get("sizes")

    logger.info(f"标题: {title} | 图片: {image_path}")
    logger.info(f"面料: {material} | 颜色: {color} | 风格: {style}")
    logger.info(f"价格: {price} | 尺码: {sizes}")

    # 1. 上传图片
    image_files = get_images_from_folder(str(image_path)) if image_path else []
    if image_files:
        await upload_images(page, image_files)
    else:
        logger.warning(f"路径 {image_path} 下未找到图片")

    # 2. 填写标题
    if title:
        await fill_title(page, title)

    # 3. 点击下一步
    if title or image_files:
        await click_next_button(page)
        await page.wait_for_timeout(3000)

        # 4. 填写面料材质
        if material:
            await fill_input_field(page, "面料材质", str(material), "面料材质")

        # 5. 填写颜色（支持多个）
        if color:
            colors = [c.strip() for c in str(color).split(",") if c.strip()]
            await fill_colors(page, colors)

        # 6. 选择风格
        if style:
            await select_style(page, str(style))

        # 7. 填写尺码（支持多个）
        if sizes:
            size_list = [s.strip() for s in str(sizes).split() if s.strip()]
            await fill_sizes(page, size_list)

        # 8. 填写售卖价
        if price:
            await fill_price(page, float(price))

        # 9. 填写库存（固定10）
        await fill_stock_default(page, 10)

    await page.wait_for_timeout(3000)
    logger.info(f"第 {index} 条处理完成")


async def run_uploader():
    """批量上架商品到视频号小店"""
    if not os.path.exists(SHIPINHAO_STATE_FILE):
        logger.error(f"未找到 {SHIPINHAO_STATE_FILE}，请先运行登录")
        return

    data = read_upload_data(SHIPINHAO_UPLOAD_EXCEL, UPLOAD_COLUMNS)
    if not data:
        logger.error("无可用上架数据")
        return

    logger.info(f"共 {len(data)} 条商品待上架")

    async with async_playwright() as p:
        browser = await launch_browser(p, channel=BROWSER_CHANNEL)
        context = await create_context(
            browser, state_file=SHIPINHAO_STATE_FILE, no_viewport=True
        )
        page = await context.new_page()

        for i, item in enumerate(data, 1):
            # 每条商品都导航到发布页
            await page.goto(SHIPINHAO_GOODS_URL)
            logger.info("等待页面及微应用加载...")
            await asyncio.sleep(5)
            await handle_popups(page)

            try:
                await page.wait_for_selector(SHIPINHAO_MICRO_APP, timeout=20000)
                logger.info("微应用已就绪")
            except Exception:
                logger.error("微应用加载超时，请检查登录状态")
                continue

            await process_single_item(page, item, i)

            if i < len(data):
                logger.info("准备处理下一条商品...")
                await page.wait_for_timeout(2000)

        logger.info(f"\n全部上架完成！共处理 {len(data)} 条商品")
        input("按回车关闭浏览器...")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(run_uploader())
