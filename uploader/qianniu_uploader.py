import asyncio
import json
import os
import re
import random
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.async_api import async_playwright, Page
from utils.browser import launch_browser, create_context, handle_popups
from utils.excel import read_upload_data
from utils.image import get_images_from_folder
from utils.logger import setup_logger
from config import (
    QIANNIU_STATE_FILE, BROWSER_CHANNEL,
    QIANNIU_UPLOAD_EXCEL, QIANNIU_UPLOAD_COLUMNS,
    QIANNIU_GOODS_URL, DESKTOP_PATH,
)

logger = setup_logger("qianniu_uploader")


async def is_page_closed(page: Page) -> bool:
    """检查页面是否已关闭"""
    try:
        return page.is_closed()
    except:
        return True


async def check_and_relogin(page: Page, context):
    """检查登录状态，失效则触发重新登录"""
    try:
        current_url = page.url
        if "login" in current_url or "passport" in current_url:
            logger.warning("检测到登录页面，登录状态可能已失效")
            from login.qianniu_login import login_interactive
            success = await login_interactive(page, context, QIANNIU_STATE_FILE)
            return success
        return True
    except Exception as e:
        logger.error(f"登录状态检查失败: {e}")
        return False


# ==================== 人工模拟工具函数 ====================
async def human_type(page: Page, text: str, min_delay: int = 50, max_delay: int = 150):
    """模拟人工逐字输入，每个字符间有随机延迟（毫秒）"""
    for char in str(text):
        await page.keyboard.type(char, delay=random.randint(min_delay, max_delay))
        # 偶尔加一个稍长的停顿，模拟人思考
        if random.random() < 0.1:
            await page.wait_for_timeout(random.randint(200, 500))


async def human_clear_and_type(page: Page, locator, text: str):
    """模拟人工清空输入框并输入文本：三击全选 → 删除 → 逐字输入"""
    await locator.click()
    await page.wait_for_timeout(random.randint(200, 400))
    # 三击全选
    await locator.click(click_count=3)
    await page.wait_for_timeout(random.randint(100, 300))
    await page.keyboard.press("Backspace")
    await page.wait_for_timeout(random.randint(200, 400))
    await human_type(page, text)


async def wait_and_click_enabled(page: Page, locator, timeout: int = 10000, desc: str = "按钮"):
    """等待按钮可见且可用（非 disabled）后再点击"""
    await locator.wait_for(state="visible", timeout=timeout)
    # 轮询等待 enabled
    deadline = asyncio.get_event_loop().time() + timeout / 1000
    while asyncio.get_event_loop().time() < deadline:
        if await is_page_closed(page):
            return False
        try:
            is_disabled = await locator.is_disabled()
            if not is_disabled:
                # 点击前加一个小随机延迟
                await page.wait_for_timeout(random.randint(200, 600))
                await locator.click()
                logger.info(f"已点击{desc}")
                return True
        except:
            pass
        await page.wait_for_timeout(500)

    logger.warning(f"{desc}在 {timeout}ms 内未变为可用状态，尝试强制点击")
    await locator.click(force=True)
    return True


async def random_pause(page: Page, min_ms: int = 500, max_ms: int = 1500):
    """随机等待，模拟人工操作间隔"""
    await page.wait_for_timeout(random.randint(min_ms, max_ms))


# ==================== 步骤 1: 关闭弹窗 ====================
async def dismiss_modal_popup(page: Page):
    """关闭页面上可能存在的模态弹窗"""
    if await is_page_closed(page):
        return False

    try:
        popup_btn = page.locator("xpath=//div[contains(@class,'currentHover')]//button[contains(@class,'model-button')]")
        if await popup_btn.is_visible(timeout=5000):
            await popup_btn.click()
            logger.info("已关闭模态弹窗")
            await page.wait_for_timeout(1000)
            return True
        else:
            logger.info("未检测到模态弹窗，继续")
            return True
    except Exception as e:
        logger.info(f"弹窗检测完成（无弹窗或已处理）: {e}")
        return True


# ==================== 步骤 2: 上传主图 ====================
async def upload_main_images(page: Page, image_files: list[str]):
    """上传主图：点击'从本地上传' → 选择文件 → 点击确认"""
    if await is_page_closed(page):
        return False

    logger.info(f"准备上传 {len(image_files)} 张主图...")

    try:
        upload_btn = page.locator("xpath=//button[span[text()='从本地上传']]").first
        await upload_btn.wait_for(state="visible", timeout=15000)

        async with page.expect_file_chooser(timeout=10000) as fc_info:
            await upload_btn.click()

        file_chooser = await fc_info.value
        await file_chooser.set_files(image_files)
        logger.info(f"已选择 {len(image_files)} 张图片，等待上传完成...")

        # 等待上传完成（轮询检测进度条消失）
        for wait_i in range(30):
            await page.wait_for_timeout(1000)
            try:
                progress = page.locator('xpath=//div[contains(@class,"progress") or contains(@class,"loading") or contains(@class,"uploading")]')
                if await progress.count() == 0:
                    logger.info(f"图片上传完成 (等待 {wait_i + 1}s)")
                    break
            except:
                pass
        else:
            logger.info("上传进度检测超时，使用固定等待 5s")
            await page.wait_for_timeout(5000)

        # 点击确认按钮
        confirm_btn = page.locator('xpath=//div[@class="ai-category-image-mode-footer"]//button[contains(@class,"next-btn-primary")]')
        await wait_and_click_enabled(page, confirm_btn, timeout=15000, desc="图片确认按钮")
        await random_pause(page, 2000, 4000)

        return True
    except Exception as e:
        logger.error(f"主图上传失败: {e}")
        return False


# ==================== 步骤 3: 选择品牌 ====================
async def select_brand(page: Page):
    """选择品牌：点击品牌输入框 → 搜索'无品牌' → 选择 → 确认"""
    if await is_page_closed(page):
        return False

    try:
        brand_input = page.locator(
            "xpath=//span[text()='品牌' or @title='品牌']"
            "/ancestor::div[contains(@class,'sell-component-info-wrapper-wrap')]"
            "//*[self::input or self::select]"
        ).first
        await brand_input.wait_for(state="visible", timeout=10000)
        await brand_input.click()
        logger.info("已点击品牌输入框")
        await random_pause(page, 800, 1500)

        # 在搜索框输入"无品牌"
        search_input = page.locator('xpath=//div[contains(@class,"options-search")]/span/input').first
        await search_input.wait_for(state="visible", timeout=5000)
        await search_input.click()
        await random_pause(page, 300, 600)
        await human_type(page, "无品牌")
        logger.info("已输入'无品牌'")
        await random_pause(page, 1000, 2000)

        # 点击"无品牌"选项
        option = page.locator('xpath=//div[text()="无品牌"]/ancestor::div[@class="options-item"]').first
        await option.wait_for(state="visible", timeout=5000)
        await random_pause(page, 300, 800)
        await option.click()
        logger.info("已选择'无品牌'")
        await random_pause(page, 1000, 2000)

        # 点击确认按钮（等待可用）
        try:
            confirm_btn = page.locator('xpath=//button[span[text()="确认"] or span[text()="确定"]]').first
            await wait_and_click_enabled(page, confirm_btn, timeout=5000, desc="品牌确认按钮")
            await random_pause(page, 1000, 2000)
        except:
            pass

        return True
    except Exception as e:
        logger.error(f"选择品牌失败: {e}")
        return False


# ==================== 步骤 4: 属性名称填写 ====================
async def fill_attribute_fields(page: Page, item: dict):
    """遍历所有属性名称字段，判断是否已填写，未填写则输入"""
    if await is_page_closed(page):
        return False

    logger.info("开始填写属性字段...")

    # 映射 Excel 字段到淘宝属性名称
    attr_mapping = {
        "style": "风格",
        "season": "适用季节",
        "fabric": "面料",
        "material_composition": "材质成分",
        "safety_level": "安全等级",
    }

    for key, attr_name in attr_mapping.items():
        value = item.get(key)
        if not value:
            continue

        try:
            await fill_single_attribute(page, attr_name, str(value))
        except Exception as e:
            logger.warning(f"填写属性 {attr_name} 失败: {e}")

    return True


async def fill_single_attribute(page: Page, attr_name: str, attr_value: str):
    """填写单个属性字段

    逻辑：
    - 定位包含该属性名称的容器
    - 检测 //em 是否存在（已填写则跳过）
    - 否则点击 //input，判断是否出现搜索下拉框
      - 有搜索框：在搜索框输入值 → 选择匹配项
      - 无搜索框：直接在 input 中输入
    """
    if await is_page_closed(page):
        return False

    try:
        container = page.locator(
            f'xpath=//div[contains(@id,"sell-field-p-") and .//span[@title="{attr_name}"]]'
        ).first

        if not await container.is_visible(timeout=3000):
            logger.info(f"未找到属性字段: {attr_name}，跳过")
            return True

        # 检测是否已有 em 标签（表示已填写）
        em_tag = container.locator("xpath=.//em")
        if await em_tag.count() > 0 and await em_tag.first.is_visible(timeout=1000):
            logger.info(f"属性 {attr_name} 已填写，跳过")
            return True

        # 点击 input
        input_field = container.locator("xpath=.//input").first
        await input_field.wait_for(state="visible", timeout=3000)
        await input_field.click()
        logger.info(f"已点击属性 {attr_name} 输入框")
        await random_pause(page, 800, 1500)

        # 检测是否出现搜索下拉框
        search_input = page.locator('xpath=//div[contains(@class,"options-search")]/span/input').first
        if await search_input.is_visible(timeout=2000):
            # 有搜索框：输入值并选择
            await search_input.click()
            await random_pause(page, 200, 500)
            await human_type(page, attr_value)
            logger.info(f"已在搜索框输入: {attr_value}")
            await random_pause(page, 1000, 2000)

            # 选择匹配的选项
            option = page.locator(f'xpath=//div[text()="{attr_value}"]/ancestor::div[@class="options-item"]').first
            if await option.is_visible(timeout=3000):
                await random_pause(page, 300, 800)
                await option.click()
                logger.info(f"已选择属性值: {attr_value}")
            else:
                # 尝试模糊匹配
                option_fuzzy = page.locator(f'xpath=//div[contains(text(),"{attr_value}")]/ancestor::div[@class="options-item"]').first
                if await option_fuzzy.is_visible(timeout=2000):
                    await random_pause(page, 300, 800)
                    await option_fuzzy.click()
                    logger.info(f"已模糊选择属性值: {attr_value}")
                else:
                    logger.warning(f"未找到匹配选项: {attr_value}")
        else:
            # 无搜索框：直接在 input 中输入
            await human_clear_and_type(page, input_field, attr_value)
            logger.info(f"已直接输入属性值: {attr_value}")

        await random_pause(page, 800, 1500)
        return True

    except Exception as e:
        logger.warning(f"填写属性 {attr_name}={attr_value} 失败: {e}")
        return False


# ==================== 步骤 5: 输入标题 ====================
async def fill_title(page: Page, title: str):
    """填写宝贝标题"""
    if await is_page_closed(page):
        return False

    try:
        title_input = page.locator(
            'xpath=//span[@title="宝贝标题"]'
            '/ancestor::div[contains(@class,"sell-component-info-wrapper")]'
            '//input'
        ).first
        await title_input.wait_for(state="visible", timeout=10000)
        await human_clear_and_type(page, title_input, title)
        logger.info(f"已填写标题: {title}")
        await random_pause(page, 800, 1500)
        return True
    except Exception as e:
        logger.error(f"填写标题失败: {e}")
        return False


# ==================== 步骤 6: 填写颜色 + 上传颜色图片 ====================
async def fill_colors_and_images(page: Page, colors: list[str], color_image_paths: list[str]):
    """填写颜色分类并上传对应颜色图片

    流程：
    1. 第一个颜色填入 //input[@placeholder="主色(必选)"]
    2. 后续颜色点击添加按钮新增输入框后填写
    3. 上传颜色图片：逐个点击空图片区域 → 本地上传
    """
    if await is_page_closed(page):
        return False

    logger.info(f"准备填写 {len(colors)} 个颜色: {colors}")

    for i, color in enumerate(colors):
        if await is_page_closed(page):
            return False

        try:
            if i == 0:
                # 第一个颜色填入主色输入框
                color_input = page.locator('xpath=//input[@placeholder="主色(必选)"]').first
                await color_input.wait_for(state="visible", timeout=10000)
                await color_input.click()
                await random_pause(page, 200, 500)
                await human_type(page, color)
                logger.info(f"已填写主色: {color}")
                await random_pause(page, 800, 1500)
            else:
                # 点击添加颜色按钮
                add_btn = page.locator(
                    'xpath=(//i[@class="next-icon next-icon-add next-xs next-btn-icon next-icon-alone"])[1]'
                )
                await add_btn.wait_for(state="visible", timeout=5000)
                await random_pause(page, 300, 800)
                await add_btn.click()
                logger.info(f"已点击添加颜色按钮 ({i+1}/{len(colors)})")
                await random_pause(page, 800, 1500)

                # 定位新出现的颜色输入框（最后一个空输入框）
                all_color_inputs = page.locator('xpath=//span[text()="颜色分类"]/ancestor::div[@class="common-wrap"]//input[contains(@placeholder,"")]')
                count = await all_color_inputs.count()
                if count > 0:
                    last_input = all_color_inputs.nth(count - 1)
                    await last_input.click()
                    await random_pause(page, 200, 500)
                    await human_type(page, color)
                    logger.info(f"已填写颜色 {i+1}: {color}")
                else:
                    logger.warning(f"未找到第 {i+1} 个颜色输入框")

                await random_pause(page, 800, 1500)

        except Exception as e:
            logger.warning(f"填写颜色 {i+1} ({color}) 失败: {e}")

    # 上传颜色图片
    await page.wait_for_timeout(2000)
    await upload_color_images(page, color_image_paths)

    return True


async def upload_color_images(page: Page, color_image_paths: list[str]):
    """逐个上传颜色分类图片

    每个颜色对应一个空图片区域，点击后通过'本地上传'选择文件
    """
    if await is_page_closed(page):
        return False

    if not color_image_paths:
        logger.info("无颜色图片需要上传")
        return True

    logger.info(f"准备上传 {len(color_image_paths)} 张颜色图片")

    # 获取所有空图片上传区域
    empty_slots = page.locator(
        'xpath=//span[text()="颜色分类"]'
        '/ancestor::div[@class="common-wrap"]'
        '//div[@class="sell-color-option-image-empty"]'
    )
    slot_count = await empty_slots.count()
    logger.info(f"检测到 {slot_count} 个颜色图片上传位置")

    for i, img_path in enumerate(color_image_paths):
        if await is_page_closed(page):
            return False

        if i >= slot_count:
            logger.warning(f"颜色图片 {i+1} 超出可用上传位置，跳过")
            break

        # 获取该路径下的第一张图片
        images = get_images_from_folder(img_path)
        if not images:
            logger.warning(f"颜色图片路径无有效图片: {img_path}")
            continue

        image_file = images[0]

        try:
            # 点击空图片区域
            await empty_slots.nth(i).click()
            logger.info(f"已点击第 {i+1} 个颜色图片区域")
            await page.wait_for_timeout(1000)

            # 点击'本地上传'按钮
            local_upload_btn = page.locator("xpath=//button[span[text()='本地上传']]").first
            await local_upload_btn.wait_for(state="visible", timeout=5000)

            async with page.expect_file_chooser(timeout=10000) as fc_info:
                await local_upload_btn.click()

            file_chooser = await fc_info.value
            await file_chooser.set_files(image_file)
            logger.info(f"已上传颜色图片 {i+1}: {os.path.basename(image_file)}")

            # 等待上传完成
            await page.wait_for_timeout(3000)

        except Exception as e:
            logger.warning(f"上传颜色图片 {i+1} 失败: {e}")

    return True


# ==================== 步骤 7: 选择尺码 ====================
def clean_sizes(sizes_text: str) -> list[str]:
    """清洗尺码数据，只保留数字"""
    cleaned = re.sub(r"[\[\]'\"]", "", str(sizes_text))
    sizes = re.findall(r'\d+', cleaned)
    return sizes


async def select_sizes(page: Page, sizes: list[str]):
    """选择尺码：点击尺码输入框 → 逐个勾选 checkbox → 确定

    sizes: 只包含数字的列表，如 ['90', '100', '110', '120']
    """
    if await is_page_closed(page):
        return False

    logger.info(f"准备选择 {len(sizes)} 个尺码: {sizes}")

    try:
        # 点击尺码输入框打开选择面板
        size_input = page.locator(
            'xpath=//div[contains(@id,"struct-p-")]//input[@placeholder="请选择尺码"]'
        ).first
        await size_input.wait_for(state="visible", timeout=10000)
        await size_input.click()
        logger.info("已打开尺码选择面板")
        await random_pause(page, 1000, 2000)

        # 逐个勾选尺码 checkbox
        for size in sizes:
            try:
                checkbox_label = page.locator(
                    f'xpath=//label[span[@class="next-checkbox-label" and text()="{size}cm"]]'
                )
                if await checkbox_label.is_visible(timeout=2000):
                    await random_pause(page, 300, 800)
                    await checkbox_label.click()
                    logger.info(f"已勾选尺码: {size}cm")
                    await random_pause(page, 400, 900)
                else:
                    logger.warning(f"未找到尺码选项: {size}cm")
            except Exception as e:
                logger.warning(f"勾选尺码 {size}cm 失败: {e}")

        # 点击确定（等待可用）
        confirm_btn = page.locator('xpath=//button[span[text()="确定"]]').first
        await wait_and_click_enabled(page, confirm_btn, timeout=10000, desc="尺码确定按钮")
        await random_pause(page, 1000, 2000)

        return True
    except Exception as e:
        logger.error(f"选择尺码失败: {e}")
        return False


# ==================== 步骤 8: 尺码映射 ====================
async def select_size_mapping(page: Page):
    """选择尺码映射：点击下拉框 → 选择'童装通用'"""
    if await is_page_closed(page):
        return False

    try:
        mapping_input = page.locator(
            'xpath=//div[@id="sell-field-sizeMapping"]//input[@role="combobox" and @placeholder="请选择"]'
        ).first
        await mapping_input.wait_for(state="visible", timeout=10000)
        await mapping_input.click()
        logger.info("已点击尺码映射下拉框")
        await random_pause(page, 1000, 2000)

        option = page.locator('xpath=//div[text()="童装通用"]').first
        await option.wait_for(state="visible", timeout=5000)
        await random_pause(page, 300, 800)
        await option.click()
        logger.info("已选择尺码映射: 童装通用")
        await random_pause(page, 800, 1500)

        return True
    except Exception as e:
        logger.error(f"选择尺码映射失败: {e}")
        return False


# ==================== 步骤 9: 价格库存批量填写 ====================
async def fill_price_stock(page: Page, price: str, stock: int = 10):
    """填写价格和库存，然后点击批量填写"""
    if await is_page_closed(page):
        return False

    try:
        # 填写价格
        price_input = page.locator('xpath=//input[@id="skuPrice"]').first
        await price_input.wait_for(state="visible", timeout=10000)
        await human_clear_and_type(page, price_input, str(price))
        logger.info(f"已填写价格: {price}")
        await random_pause(page, 500, 1000)

        # 填写库存
        stock_input = page.locator('xpath=//input[@id="skuStock"]').first
        await stock_input.wait_for(state="visible", timeout=5000)
        await human_clear_and_type(page, stock_input, str(stock))
        logger.info(f"已填写库存: {stock}")
        await random_pause(page, 500, 1000)

        # 点击批量填写（等待可用）
        batch_btn = page.locator('xpath=//button[span[text()="批量填写"]]').first
        await wait_and_click_enabled(page, batch_btn, timeout=10000, desc="批量填写按钮")
        await random_pause(page, 1500, 3000)

        return True
    except Exception as e:
        logger.error(f"填写价格库存失败: {e}")
        return False


# ==================== 主处理流程 ====================
async def process_single_item(page: Page, item: dict, index: int):
    """处理单个商品上架（完整10步流程）"""
    logger.info(f"\n{'='*60}")
    logger.info(f"--- 正在处理第 {index} 条商品 ---")

    title = item.get("title")
    sale_price = item.get("sale_price")
    color = item.get("color")
    image_path = item.get("image_path")
    color_image_paths = item.get("color_image_paths", "")
    sizes = item.get("sizes", "")

    logger.info(f"标题: {title}")
    logger.info(f"售价: {sale_price}")
    logger.info(f"颜色: {color}")
    logger.info(f"尺码: {sizes}")

    if await is_page_closed(page):
        return False

    # 步骤 1: 关闭弹窗
    await dismiss_modal_popup(page)

    # 步骤 2: 上传主图
    image_files = get_images_from_folder(str(image_path)) if image_path else []
    if image_files:
        result = await upload_main_images(page, image_files)
        if not result:
            logger.error("主图上传失败")
            return False
    else:
        logger.warning("无主图可上传")
        return False

    # 等待页面加载完成（图片识别类目等）
    await random_pause(page, 4000, 7000)

    # 步骤 3: 选择品牌
    await select_brand(page)
    await random_pause(page, 1000, 2000)

    # 步骤 4: 填写属性字段
    await fill_attribute_fields(page, item)
    await random_pause(page, 1000, 2000)

    # 步骤 5: 填写标题
    if title:
        await fill_title(page, title)
        await random_pause(page, 1000, 2000)

    # 步骤 6: 填写颜色 + 上传颜色图片
    if color:
        colors = [c.strip() for c in str(color).split() if c.strip()]
        spec_image_paths = []
        if color_image_paths:
            spec_image_paths = [p.strip() for p in str(color_image_paths).split() if p.strip()]
        await fill_colors_and_images(page, colors, spec_image_paths)
        await random_pause(page, 1000, 2000)

    # 步骤 7: 选择尺码
    if sizes:
        size_list = clean_sizes(str(sizes))
        if size_list:
            await select_sizes(page, size_list)
            await random_pause(page, 1000, 2000)

    # 步骤 8: 尺码映射
    await select_size_mapping(page)
    await random_pause(page, 1000, 2000)

    # 步骤 9: 价格库存批量填写
    if sale_price:
        await fill_price_stock(page, str(sale_price), 10)

    # 步骤 10: 等待手动检查（不自动提交）
    logger.info(f"第 {index} 条商品填写完成，等待手动检查...")
    await page.wait_for_timeout(2000)
    logger.info(f"第 {index} 条处理完成")
    return True


async def run_uploader():
    """千牛批量上架入口"""

    # 检查登录状态文件
    if not os.path.exists(QIANNIU_STATE_FILE):
        logger.error(f"未找到登录状态文件: {QIANNIU_STATE_FILE}")
        logger.error("请先执行: python main.py login qianniu")
        return

    # 读取上架数据
    data = read_upload_data(QIANNIU_UPLOAD_EXCEL, QIANNIU_UPLOAD_COLUMNS)
    if not data:
        logger.error("无可用上架数据，请检查 Excel 文件")
        return

    logger.info(f"共 {len(data)} 条商品待上架到千牛")

    results = []

    async with async_playwright() as p:
        browser = await launch_browser(p, channel=BROWSER_CHANNEL)
        context = await create_context(browser, state_file=QIANNIU_STATE_FILE, no_viewport=True)
        page = await context.new_page()

        for i, item in enumerate(data, 1):
            max_retries = 2
            success = False

            for retry in range(max_retries + 1):
                try:
                    # 导航到发品页
                    await page.goto(QIANNIU_GOODS_URL, wait_until="domcontentloaded")
                    await asyncio.sleep(3)

                    # 检查登录状态
                    login_ok = await check_and_relogin(page, context)
                    if not login_ok:
                        logger.error("登录失败，终止上架")
                        break

                    await handle_popups(page)

                    result = await process_single_item(page, item, i)

                    if result is None:
                        if retry < max_retries:
                            logger.warning(f"第 {i} 条第 {retry+1} 次异常，重启浏览器重试...")
                            await browser.close()
                            browser = await launch_browser(p, channel=BROWSER_CHANNEL)
                            context = await create_context(browser, state_file=QIANNIU_STATE_FILE, no_viewport=True)
                            page = await context.new_page()
                            continue
                        else:
                            logger.error(f"第 {i} 条重试 {max_retries} 次仍失败，跳过")
                            success = False
                    else:
                        success = result
                    break

                except Exception as e:
                    logger.error(f"处理第 {i} 条出错: {e}")
                    if await is_page_closed(page):
                        logger.info("浏览器已被手动关闭，停止执行")
                        results.append({"index": i, "title": item.get("title", ""), "success": False})
                        break
                    success = False
                    break
            else:
                results.append({
                    "index": i,
                    "title": item.get("title", ""),
                    "success": success,
                })
                if i < len(data):
                    await page.wait_for_timeout(2000)
                continue

            # break 出来的情况
            if await is_page_closed(page):
                results.append({"index": i, "title": item.get("title", ""), "success": False})
                break

            results.append({
                "index": i,
                "title": item.get("title", ""),
                "success": success,
            })

            if i < len(data):
                await page.wait_for_timeout(2000)

        # 汇总
        success_count = sum(1 for r in results if r.get("success"))
        failed_count = sum(1 for r in results if not r.get("success"))
        logger.info(f"\n{'='*60}")
        logger.info(f"全部完成！共处理 {len(data)} 条，成功 {success_count}，失败 {failed_count}")

        # 保存结果 JSON
        result_file = os.path.join(
            DESKTOP_PATH,
            f"qianniu_upload_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        )
        with open(result_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "total": len(data),
                    "success": success_count,
                    "failed": failed_count,
                    "results": results,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

        logger.info(f"结果已保存到: {result_file}")
        await page.wait_for_timeout(50000000)
        await browser.close()
        logger.info("浏览器已关闭")


if __name__ == "__main__":
    asyncio.run(run_uploader())
