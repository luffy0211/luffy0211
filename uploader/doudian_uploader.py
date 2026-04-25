import asyncio
import os
import sys
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.async_api import async_playwright, Page
from utils.browser import launch_browser, create_context, handle_popups
from utils.excel import read_upload_data
from utils.image import get_images_from_folder
from utils.logger import setup_logger
from config import (
    DOUDIAN_STATE_FILE, BROWSER_CHANNEL,
    DOUDIAN_UPLOAD_EXCEL, DOUDIAN_UPLOAD_COLUMNS,
    DOUDIAN_GOODS_URL, DOUDIAN_LOGIN_URL, DESKTOP_PATH,
)

logger = setup_logger("doudian_uploader")


async def is_page_closed(page: Page) -> bool:
    """检查页面是否已关闭"""
    try:
        return page.is_closed()
    except:
        return True


async def check_and_relogin(page: Page, context):
    """检查登录状态，失效则触发重新登录"""
    try:
        # 检测是否在登录页（URL 包含 login 或页面有登录按钮）
        current_url = page.url
        if "login" in current_url or "passport" in current_url:
            logger.warning("检测到登录页面，登录状态可能已失效")
            from login.doudian_login import login_interactive
            success = await login_interactive(page, context, DOUDIAN_STATE_FILE)
            return success
        return True
    except Exception as e:
        logger.error(f"登录状态检查失败: {e}")
        return False


async def upload_main_images(page: Page, image_files: list[str]):
    """上传主图：点击上传区域 → 上传本地图片 → 点击确认"""
    if await is_page_closed(page):
        return False

    logger.info(f"准备上传 {len(image_files)} 张主图...")
    await page.wait_for_timeout(3000)

    try:
        
        try:
            select_files_wrapper = page.locator("//div[contains(@class,'material-upload-button') and contains(.,'商品正面图')]").first
            await select_files_wrapper.wait_for(state="visible", timeout=5000)

            async with page.expect_file_chooser(timeout=10000) as fc_info:
                await select_files_wrapper.click()

            file_chooser = await fc_info.value
            await file_chooser.set_files(image_files)
            logger.info("图片已选择，等待上传完成...")

            # 轮询等待图片上传完成（进度条消失 / 缩略图全部出现）
            uploaded = False
            for wait_i in range(30):
                await page.wait_for_timeout(1000)
                try:
                    # 检查是否还有上传中的进度条/loading
                    progress = page.locator('xpath=//div[contains(@class,"material-upload-button")]//div[contains(@class,"progress") or contains(@class,"loading") or contains(@class,"uploading")]')
                    if await progress.count() == 0:
                        uploaded = True
                        logger.info(f"图片上传完成 (等待 {wait_i + 1}s)")
                        break
                except Exception:
                    pass

            if not uploaded:
                logger.info("上传进度检测超时，使用固定等待 8s")
                await page.wait_for_timeout(8000)

        except Exception as e:
            logger.error(f"点击上传区域失败: {e}")
            return False

       
    except Exception as e:
        logger.error(f"主图上传失败: {e}")
        return False


async def generate_title_ai(page: Page):
    """智能生成标题：等待'立即使用'按钮出现并点击"""
    if await is_page_closed(page):
        return False
    try:
        use_btn = page.locator('xpath=//a[normalize-space()="立即使用"]').first
        await use_btn.wait_for(state="visible", timeout=15000)
        await use_btn.click()
        logger.info("已点击'立即使用'，标题已应用")
        return True
    except Exception as e:
        logger.warning(f"智能生成标题失败（'立即使用'未出现或点击失败）: {e}")
        try:
            ai_ioc = page.locator('xpath=//div[@id="goods-title-wrapper"]//span[@class="ecom-g-input-suffix"]/span/img').first
            await ai_ioc.click()
            await page.wait_for_timeout(2000)
            first_recommend = page.locator('xpath=//li[1]//span[contains(@style,"rgb(86, 89, 96)")]').first
            await first_recommend.click()
            logger.info("已点击推荐标题")   
            return True
        except:
            pass
        await page.wait_for_timeout(5000)
        logger.warning("标题输入框不可见，可能未生成标题")
        return False


async def wait_category_ready(page: Page, max_wait: int = 20):
    """等待类目加载"""
    if await is_page_closed(page):
        return False

    for i in range(max_wait):
        try:
            category = page.locator('text=已选类目').first
            if await category.is_visible(timeout=1000):
                logger.info("类目加载完成")
                return True
        except:
            pass
        await page.wait_for_timeout(1000)

    logger.warning("类目加载超时")
    return False


async def click_confirm_next(page: Page):
    """点击信息已确认，下一步"""
    if await is_page_closed(page):
        return False

    try:
        next_btn = page.locator('xpath=//span[text()="下一步"]').first

        for attempt in range(30):
            if await is_page_closed(page):
                return False
            try:
                if await next_btn.is_visible() and await next_btn.is_enabled():
                    await next_btn.click()
                    logger.info("已点击下一步")
                    await page.wait_for_timeout(3000)
                    return True
            except:
                pass
            await page.wait_for_timeout(500)

        return False
    except Exception as e:
        logger.error(f"点击下一步失败: {e}")
        return False


async def fill_title_manual(page: Page, title: str):
    """手动填写商品标题"""
    if await is_page_closed(page):
        return False

    try:
        title_input = page.locator('xpath=//input[@id="pg-title-input"]').first
        await title_input.wait_for(state="visible", timeout=10000)
        await title_input.click()
        await title_input.fill(title)
        logger.info(f"已填写标题: {title}")
        return True
    except Exception as e:
        logger.error(f"填写标题失败: {e}")
        return False





async def set_presale_mode(page: Page, days: int = 15):
    """设置预售模式"""
    if await is_page_closed(page):
        return False

    try:
        presale_radio = page.locator('xpath=//span[text()="现货预售混合"]').first
        if await presale_radio.is_visible(timeout=5000):
            await presale_radio.click()
            logger.info("已设置预售模式")
            await page.wait_for_timeout(1000)

        days_input = page.locator('xpath=//div[@attr-field-id="预售发货时间"]//input[@value="15"]').first
        if await days_input.is_visible(timeout=5000):
            await days_input.click()
            # await days_input.fill(str(days))
            logger.info("已选择15天内")

        return True
    except Exception as e:
        logger.error(f"设置预售模式失败: {e}")
        return False





async def handle_size_template(page: Page, size_format: str = "通用"):
    """处理尺码信息模板选择或图片识别上传"""
    if await is_page_closed(page):
        return False

    try:
        template_selector = 'xpath=(//div[@attr-field-id="尺码表"]//div[text()="尺码模板"]/following::input[@role="combobox"])[1]'
        template_element = page.locator(template_selector)
        

        if not await template_element.is_visible(timeout=3000):
            logger.info("未找到尺码信息模板选择器，跳过")
            return True

        logger.info("找到尺码信息模板选择器")

        # 点击模板选择器打开下拉框
        await template_element.click()
        await page.wait_for_timeout(1000)

        # 检查是否存在指定格式的选项
        option_xpath = f'//div[contains(@class,"ecom-g-select-item-option") and contains(text(),"{size_format}")]'
        option = page.locator(f'xpath={option_xpath}')


        if await option.is_visible(timeout=2000):
            await option.click()
            logger.info(f"已选择尺码模板: {size_format}")
            await page.wait_for_timeout(1000)
            return True

        # 不存在选项，使用图片识别上传
        logger.info(f"未找到尺码模板 {size_format}，使用图片识别上传")

        upload_btn = page.locator('xpath=//div[@id="anchor-尺码信息"]//button[contains(.,"上传图片识别")]')
        await upload_btn.click()
        logger.info("已点击上传图片识别")
        await page.wait_for_timeout(2000)

        search_input = page.locator('xpath=//div[@class="combine-search"]//input[@placeholder="输入关键词"]')
        await search_input.fill("尺码格式")
        logger.info("已输入搜索关键词: 尺码格式")
        await page.wait_for_timeout(500)

        search_btn = page.locator('xpath=//div[@class="combine-search"]//button[contains(@class,"combine-button")]//span[text()=" 搜索 "]')
        await search_btn.click()
        logger.info("已点击搜索")
        await page.wait_for_timeout(2000)

        image = page.locator('xpath=//div[@class="material-images-wrapper"]//img[@class="card-image"]').first
        await image.click()
        logger.info("已选择图片")
        await page.wait_for_timeout(1000)

        confirm_drawer = page.locator('xpath=//div[@class="d-drawer-footer"]//button[contains(.,"确认")]')
        await confirm_drawer.click()
        logger.info("已点击确认（抽屉）")
        await page.wait_for_timeout(1500)

        confirm_modal = page.locator('xpath=//div[contains(@class,"d-modal-footer")]//button[normalize-space()="确定"]')
        await confirm_modal.click()
        logger.info("已点击确定（弹窗）")
        await page.wait_for_timeout(1000)

        return True

    except Exception as e:
        logger.error(f"处理尺码信息模板失败: {e}")
        return False


async def fill_colors(page: Page, colors: list[str]):
    """填写颜色：按顺序向已生成的输入框填写，点击 → 创建类型 → 输入 → 回车 → 确定"""
    if await is_page_closed(page):
        return False

    logger.info(f"准备填写 {len(colors)} 个颜色: {colors}")

    for i, color in enumerate(colors):
        if await is_page_closed(page):
            return False

        try:
            # 1. 按索引顺序点击对应的颜色输入框（上传规格图后已生成多个）
            color_inputs = page.locator('xpath=//div[contains(@class,"style_skuValue__")]//input[@placeholder="请选择/输入颜色分类"]')
            count = await color_inputs.count()
            logger.info(f"当前颜色输入框数量: {count}")

            if count > 0:
                await color_inputs.first.click()
            else:
                logger.warning(f"第 {i+1} 个颜色输入框不存在")
                continue

            logger.info(f"已点击颜色分类输入框 ({i+1}/{len(colors)})")
            await page.wait_for_timeout(1000)

            # 2. 点击"创建类型"（取最后一个）
            create_type_btn = page.locator('xpath=(//span[contains(@class,"styles_newSKU")]//a[text()="创建类型"])[last()]').first
            await create_type_btn.wait_for(state="visible", timeout=5000)
            await create_type_btn.click()
            logger.info(f"已点击创建类型 ({i+1}/{len(colors)})")
            await page.wait_for_timeout(1000)

            # 3. 输入颜色并回车
            await page.keyboard.type(color, delay=80)
            await page.keyboard.press('Enter')
            await page.wait_for_timeout(1000)

            # 4. 点击确定按钮（可能不每次都出现，短超时）
            try:
                confirm_btn = page.locator('xpath=//div[contains(@class,"styles_popupFooter")]//button[contains(.,"确定")]')
                if await confirm_btn.is_visible(timeout=2000):
                    await confirm_btn.click()
                    logger.info(f"已点击确定")
                    await page.wait_for_timeout(1000)
            except:
                pass

            logger.info(f"已填写颜色 {i+1}: {color}")
            await page.wait_for_timeout(1500)

        except Exception as e:
            logger.warning(f"填写颜色 {i+1} 失败: {e}")

    return True


async def upload_spec_images(page: Page, image_paths: list[str]):
    """批量上传规格图"""
    if await is_page_closed(page):
        return False

    try:
        

        # 3. 选择文件
        upload_trigger = page.locator('text=批量上传规格图').first
        await upload_trigger.wait_for(state="visible", timeout=10000)

        async with page.expect_file_chooser(timeout=15000) as fc_info:
            await upload_trigger.click()

        file_chooser = await fc_info.value
        await file_chooser.set_files(image_paths)
        logger.info(f"规格图已选择 {len(image_paths)} 张")
        await page.wait_for_timeout(3000)

        # 4. 点击确认
        await page.wait_for_timeout(3000)

        

        await page.wait_for_timeout(3000)
        return True
    except Exception as e:
        logger.error(f"上传规格图失败: {e}")
        return False


async def fill_sizes(page: Page, sizes: list[str]):
    """填写尺码：点击下拉框 → 创建类型 → 输入尺码 → 回车 → 确定"""
    if await is_page_closed(page):
        return False

    logger.info(f"准备填写 {len(sizes)} 个尺码: {sizes}")

    for i, size in enumerate(sizes):
        if await is_page_closed(page):
            return False

        try:
            # 1. 点击尺码下拉框（每次用最后一个空输入框）
            size_dropdown = page.locator('xpath=//div[@id="skuValue-尺码大小"]//input[contains(@class,"ecom-g-cascader-input-multiple")]').last
            await size_dropdown.wait_for(state="visible", timeout=5000)
            await size_dropdown.click()
            logger.info(f"已点击尺码下拉框 ({i+1}/{len(sizes)})")
            await page.wait_for_timeout(1000)

            # 2. 点击"创建类型"（取最后一个）
            create_type_btn = page.locator('xpath=(//span[contains(@class,"styles_newSKU")]//a[text()="创建类型"])[last()]').first
            await create_type_btn.wait_for(state="visible", timeout=5000)
            await create_type_btn.click()
            logger.info(f"已点击创建类型 ({i+1}/{len(sizes)})")
            await page.wait_for_timeout(1000)

            # 3. 输入尺码并回车
            await page.keyboard.type(size, delay=80)
            await page.keyboard.press('Enter')
            await page.wait_for_timeout(1000)

            # 4. 点击确定按钮（可能不每次都出现，短超时）
            try:
                confirm_btn = page.locator('xpath=//div[contains(@class,"styles_popupFooter")]//button[contains(.,"确定")]')
                if await confirm_btn.is_visible(timeout=2000):
                    await confirm_btn.click()
                    logger.info(f"已点击确定")
                    await page.wait_for_timeout(1000)
            except:
                pass

            logger.info(f"已填写尺码 {i+1}: {size}")
            await page.wait_for_timeout(1500)

        except Exception as e:
            logger.warning(f"填写尺码 {i+1} 失败: {e}")

    return True


async def select_brand(page: Page):
    """选择品牌：选择无品牌"""
    if await is_page_closed(page):
        return False

    try:
        await dismiss_guide_overlay(page)

        brand_input = page.locator('xpath=//div[@attr-field-id="品牌"]//input[contains(@class,"ecom-g-select-selection-search-input")]')
        if await brand_input.is_visible(timeout=3000):
            await brand_input.click(force=True)
            await page.wait_for_timeout(500)
            await page.keyboard.type("无品牌", delay=50)
            await page.wait_for_timeout(1200)

            option = page.locator('xpath=//div[@class="ecom-g-select-item-option-content" and text()="无品牌"]')
            await option.wait_for(state="visible", timeout=3000)
            await option.click()
            logger.info("已选择品牌: 无品牌")
            await page.wait_for_timeout(500)
            return True
        else:
            logger.warning("未找到品牌输入框")
            return False
    except Exception as e:
        logger.warning(f"选择品牌失败: {e}")
        return False


async def dismiss_guide_overlay(page: Page):
    """关闭引导蒙层（ecom-guide-single-content-wrapper）"""
    try:
        guide_btns = [
            'xpath=//div[contains(@class,"ecom-guide-single-content-wrapper")]//button',
            'xpath=//div[contains(@class,"ecom-guide-single-content-wrapper")]//*[contains(text(),"知道了")]',
            'xpath=//div[contains(@class,"ecom-guide-single-content-wrapper")]//*[contains(text(),"跳过")]',
            'xpath=//div[contains(@class,"ecom-guide-single-content-wrapper")]//*[contains(text(),"我知道了")]',
        ]
        for selector in guide_btns:
            btn = page.locator(selector).first
            if await btn.is_visible(timeout=1000):
                await btn.click()
                logger.info("已关闭引导蒙层")
                await page.wait_for_timeout(500)
                return True
        overlay = page.locator('xpath=//div[contains(@class,"ecom-guide-single-content-wrapper")]')
        if await overlay.is_visible(timeout=500):
            await overlay.click()
            await page.wait_for_timeout(500)
            return True
    except:
        pass
    return False


async def fill_single_attribute(page: Page, attr_name: str, value: str):
    """填写单个下拉属性：输入 → 下拉选择，无数据则新建"""
    try:
        xpath = f'//div[@attr-field-id="{attr_name}"]//input[contains(@class,"ecom-g-select-selection-search-input")]'
        input_field = page.locator(f'xpath={xpath}')

        if not await input_field.is_visible(timeout=3000):
            logger.warning(f"未找到属性输入框: {attr_name}")
            return False

        await dismiss_guide_overlay(page)

        await input_field.click(force=True)
        await page.wait_for_timeout(500)
        await page.keyboard.type(str(value), delay=50)
        await page.wait_for_timeout(1200)

        # 尝试从下拉框选择
        option = page.locator(f'xpath=//div[@class="ecom-g-select-item-option-content" and text()="{value}"]')
        if await option.is_visible(timeout=1500):
            await option.click()
            logger.info(f"已选择{attr_name}: {value}")
            await page.wait_for_timeout(500)
            return True

        # 检查是否暂无数据
        no_data = page.locator('xpath=//div[contains(@class,"ecom-g-select-dropdown")]//div[text()="暂无数据"]')
        if await no_data.is_visible(timeout=800):
            logger.info(f"{attr_name} 暂无数据，新建")
            new_btn = page.locator(f'xpath=//span[contains(@class,"styles_newSKU") and contains(.,"新建{attr_name}")]')
            await new_btn.wait_for(state="visible", timeout=3000)
            
            await new_btn.click()
            await page.wait_for_timeout(500)

            await page.keyboard.type(str(value), delay=50)
            await page.wait_for_timeout(500)

            confirm_icon = page.locator('xpath=//div[contains(@class,"styles_addSKUNameEditWrapper")]//img[@alt="确认"]')
            await confirm_icon.wait_for(state="visible", timeout=3000)
            await confirm_icon.click()
            logger.info(f"已新建{attr_name}: {value}")
            await page.wait_for_timeout(500)
            return True

        logger.warning(f"填写{attr_name}未匹配到选项: {value}")
        return False

    except Exception as e:
        logger.warning(f"填写属性 {attr_name} 失败: {e}")
        return False


def parse_materials(material_str: str) -> list[dict]:
    """解析材质成分字符串，返回 [{name, percent}]
    
    示例输入: "棉95% 氨纶5%" 或 "聚酯纤维100%" 或 "棉80 涤纶20"
    """
    materials = []
    parts = str(material_str).split()
    for part in parts:
        part = part.strip()
        if not part:
            continue
        # 提取材质名和百分比
        match = re.match(r'([^\d%（()]+)\s*[（(]?(\d+)[%）)]?', part)
        if match:
            name = match.group(1).strip()
            percent = int(match.group(2))
            materials.append({"name": name, "percent": percent})
        else:
            # 纯文字，无百分比
            name = re.sub(r'[\d%()（）]+', '', part).strip()
            if name:
                materials.append({"name": name, "percent": 0})
    return materials


async def fill_material_composition(page: Page, material_str: str):
    """填写面料材质（材质名称 + 百分比，支持多个）
    
    规则：
    - Excel 的材质成分字段对应抖店的"面料材质"
    - 材质和百分比分开填
    - 多个材质点击"添加材质"
    - 如果材质含'其他'且占比>15%，用聚酯纤维补到<=15%
    """
    if await is_page_closed(page):
        return False

    materials = parse_materials(material_str)
    if not materials:
        logger.warning("无材质数据可填写")
        return False

    logger.info(f"解析到 {len(materials)} 个材质: {materials}")

    # 处理'其他'占比不能超过15%的规则
    processed = []
    polyester_extra = 0
    for m in materials:
        if "其他" in m["name"] and m["percent"] > 15:
            polyester_extra += m["percent"] - 15
            processed.append({"name": m["name"], "percent": 15})
        else:
            processed.append(m)

    if polyester_extra > 0:
        # 检查是否已有聚酯纤维
        found = False
        for m in processed:
            if m["name"] == "聚酯纤维":
                m["percent"] += polyester_extra
                found = True
                break
        if not found:
            processed.append({"name": "聚酯纤维", "percent": polyester_extra})
        logger.info(f"'其他'超过15%，已用聚酯纤维补充，调整后: {processed}")

    for i, mat in enumerate(processed):
        if await is_page_closed(page):
            return False

        try:
            # 第2个及之后需要点击"添加材质"
            if i > 0:
                add_btn = page.locator('xpath=//button[span[text()="添加材质"]]')
                await add_btn.wait_for(state="visible", timeout=3000)
                await add_btn.click()
                logger.info("已点击添加材质")
                await page.wait_for_timeout(1000)

            # 填写材质名称：按顺序定位第 i+1 个面料材质输入框
            mat_input = page.locator('xpath=//div[@attr-field-id="面料材质"]//input[contains(@class,"ecom-g-select-selection-search-input")]').nth(i)
            await mat_input.wait_for(state="visible", timeout=3000)
            await mat_input.click()
            await page.wait_for_timeout(500)
            await page.keyboard.type(mat["name"], delay=50)
            await page.wait_for_timeout(1200)

            # 尝试从下拉框选择
            option = page.locator(f'xpath=//div[@class="ecom-g-select-item-option-content" and text()="{mat["name"]}"]')
            if await option.is_visible(timeout=1500):
                await option.click()
                logger.info(f"已选择材质: {mat['name']}")
            else:
                # 暂无数据，点击新建
                new_btn = page.locator("xpath=//span[@class='styles_newSKU__Ow_yh']").first
                await new_btn.wait_for(state="visible", timeout=3000)
                await new_btn.click()
                await page.wait_for_timeout(300)
                await page.keyboard.type(mat["name"], delay=50)
                await page.keyboard.press('Enter')
                logger.info(f"已新建材质: {mat['name']}")

            await page.wait_for_timeout(800)

            # 填写百分比
            if mat["percent"] > 0:
                percent_input = page.locator('xpath=//div[@attr-field-id="面料材质"]//input[contains(@class,"ecom-g-input") and not(contains(@class,"select"))]').nth(i)
                await percent_input.wait_for(state="visible", timeout=3000)
                await percent_input.click()
                await percent_input.fill(str(mat["percent"]))
                logger.info(f"已填写百分比: {mat['percent']}%")

            await page.wait_for_timeout(500)

        except Exception as e:
            logger.warning(f"填写材质 {i+1} ({mat['name']}) 失败: {e}")

    return True


async def fill_product_attributes(page: Page, item: dict):
    """填写商品属性（品牌、风格、季节、面料材质、安全等级）"""
    if await is_page_closed(page):
        return False

    logger.info("开始填写商品属性...")

    # 先关闭可能存在的引导蒙层
    await dismiss_guide_overlay(page)

    # 1. 选择品牌（无品牌）
    await select_brand(page)

    # 2. 填写普通下拉属性
    simple_attrs = {
        "style": "风格",
        "season": "适用季节",
        "fabric": "面料",
        "safety_level": "安全等级",
    }

    for key, attr_name in simple_attrs.items():
        value = item.get(key)
        if not value:
            continue
        await fill_single_attribute(page, attr_name, str(value))

    # 3. 填写面料材质（材质成分，含材质名+百分比）
    material_value = item.get("material_composition")
    if material_value:
        await fill_material_composition(page, str(material_value))

    return True


async def batch_fill_price_stock(page: Page, sale_price: str, market_price: str, stock: int = 10):
    """批量填写价格库存"""
    if await is_page_closed(page):
        return False

    try:
       
        # 售价
        sale_price_input = page.locator('xpath=//div[contains(@class,"styles_inputBox__IyUnP")]//input[@placeholder="价格"]')
        if await sale_price_input.is_visible(timeout=5000):
            await sale_price_input.click()
            await sale_price_input.fill(sale_price)
            logger.info(f"已填写售价: {sale_price}")

        # 库存
        stock_input = page.locator('xpath=//div[contains(@class,"styles_inputBox__IyUnP")]//input[@placeholder="现货库存"]')
        if await stock_input.is_visible(timeout=5000):
            await stock_input.click()
            await stock_input.fill(str(stock))
            logger.info(f"已填写库存: {stock}")

    

        # 点击批量设置按钮
        batch_set_btn = page.locator('xpath=//button[contains(@class,"styles_setting__") and .//span[text()="批量设置"]]').first
        try:
            if await batch_set_btn.is_visible(timeout=5000):
                await batch_set_btn.click()
                logger.info("已点击批量设置按钮")
                await page.wait_for_timeout(2000)
        except Exception as e:
            logger.warning(f"点击批量设置按钮失败: {e}")

        await page.wait_for_timeout(1000)
        return True
    except Exception as e:
        logger.error(f"批量填写失败: {e}")
        return False


def clean_sizes(sizes_text: str) -> list[str]:
    """清洗尺码数据，只保留数字"""
    cleaned = re.sub(r"[\[\]'\"]", "", str(sizes_text))
    sizes = re.findall(r'\d+', cleaned)
    return sizes


async def process_single_item(page: Page, item: dict, index: int):
    """处理单个商品"""
    logger.info(f"\n{'='*60}")
    logger.info(f"--- 正在处理第 {index} 条商品 ---")

    image_path = item.get("image_path")
    title = item.get("title")
    color = item.get("color")
    sale_price = item.get("sale_price")
    price = item.get("price")
    color_image_paths = item.get("color_image_paths", "")
    sizes = item.get("sizes", "")

    logger.info(f"标题: {title}")
    logger.info(f"售价: {sale_price}, 原价: {price}")

    if await is_page_closed(page):
        return False

    # 1. 上传主图
    image_files = get_images_from_folder(str(image_path)) if image_path else []
    if image_files:
        await upload_main_images(page, image_files)
    else:
        logger.warning("无主图可上传")

    # 2. 点击"立即使用"
    title_generated = await generate_title_ai(page)

    # 3. 等待"更多推荐"元素出现（判断页面是否正常加载）
    try:
        more_btn = page.locator('xpath=//button[contains(@class,"ecom-g-btn-link") and .//span[text()="更多推荐"]]')
        await more_btn.wait_for(state="visible", timeout=15000)
        logger.info("已检测到'更多推荐'元素，页面加载正常")
    except:
        logger.warning("未检测到'更多推荐'元素，继续执行")
        # 检查是否跳到了登录页（真正异常才重试）
        current_url = page.url
        if "login" in current_url or "passport" in current_url:
            logger.error("页面跳转到登录页，需要重新登录")
            return None

    # 4. 点击下一步
    await click_confirm_next(page)

    # 5. 如果智能生成失败，手动填写标题
    if not title_generated and title:
        await fill_title_manual(page, title)

    # 6. 生成导购短标题
    # await generate_short_title_ai(page)

    # 7. 设置预售
    await set_presale_mode(page, 15)

    # 8. 选择尺码规格
    # await select_size_spec(page)

    # 9. 处理尺码信息模板
    await handle_size_template(page, "通用")

    # 10. 上传规格图
    if color_image_paths:
        spec_image_paths = [p.strip() for p in str(color_image_paths).split() if p.strip()]
        if spec_image_paths:
            all_spec_images = []
            for path in spec_image_paths:
                images = get_images_from_folder(path)
                all_spec_images.extend(images)

            if all_spec_images:
                await upload_spec_images(page, all_spec_images)
            else:
                logger.warning(f"规格图路径无有效图片: {spec_image_paths}")
    else:
        logger.warning("无规格图路径(color_image_paths为空)")

    # 11. 填写颜色
    if color:
        colors = [c.strip() for c in str(color).split() if c.strip()]
        await fill_colors(page, colors)

    # 12. 填写尺码
    if sizes:
        size_list = clean_sizes(str(sizes))
        if size_list:
            await fill_sizes(page, size_list)

    # 13. 填写商品属性（风格、季节、材质成分、面料、安全等级）
    await fill_product_attributes(page, item)

    # 14. 批量填写价格库存
    if sale_price and price:
        market_price = str(round(float(price) * 3, 2))
        await batch_fill_price_stock(page, str(sale_price), market_price, 10)

    # 15. 提交商品
    try:
        submit_btn = page.locator('xpath=//button[span[text()="发布商品"]]').first
        await submit_btn.click()
        logger.info("已点击提交商品")
        await page.wait_for_timeout(3000)
    except Exception as e:
        logger.error(f"提交商品失败: {e}")

    await page.wait_for_timeout(2000)
    logger.info(f"第 {index} 条处理完成")
    return True


async def run_uploader():
    """抖店批量上架入口"""

    # 检查登录状态文件
    if not os.path.exists(DOUDIAN_STATE_FILE):
        logger.error(f"未找到登录状态文件: {DOUDIAN_STATE_FILE}")
        logger.error("请先执行: python main.py login doudian")
        return

    # 读取上架数据
    data = read_upload_data(DOUDIAN_UPLOAD_EXCEL, DOUDIAN_UPLOAD_COLUMNS)
    if not data:
        logger.error("无可用上架数据，请检查 Excel 文件")
        return

    logger.info(f"共 {len(data)} 条商品待上架到抖店")

    results = []

    async with async_playwright() as p:
        browser = await launch_browser(p, channel=BROWSER_CHANNEL)
        context = await create_context(browser, state_file=DOUDIAN_STATE_FILE, no_viewport=True)
        page = await context.new_page()

        for i, item in enumerate(data, 1):
            max_retries = 2
            success = False

            for retry in range(max_retries + 1):
                try:
                    # 导航到商品发布页
                    await page.goto(DOUDIAN_GOODS_URL, wait_until="domcontentloaded")
                    await asyncio.sleep(3)

                    # 检查登录状态
                    login_ok = await check_and_relogin(page, context)
                    if not login_ok:
                        logger.error("登录失败，终止上架")
                        break

                    await handle_popups(page)

                    result = await process_single_item(page, item, i)

                    if result is None:
                        # 仅"更多推荐"元素未出现时，重启浏览器重试
                        if retry < max_retries:
                            logger.warning(f"第 {i} 条第 {retry+1} 次未检测到'更多推荐'，重启浏览器重试...")
                            await browser.close()
                            browser = await launch_browser(p, channel=BROWSER_CHANNEL)
                            context = await create_context(browser, state_file=DOUDIAN_STATE_FILE, no_viewport=True)
                            page = await context.new_page()
                            continue
                        else:
                            logger.error(f"第 {i} 条重试 {max_retries} 次仍失败，跳过")
                            success = False
                    else:
                        success = result
                    break

                except Exception as e:
                    # 手动关闭浏览器或其他异常，不重试直接退出
                    logger.error(f"处理第 {i} 条出错: {e}")
                    if await is_page_closed(page):
                        logger.info("浏览器已被手动关闭，停止执行")
                        results.append({"index": i, "title": item.get("title", ""), "success": False})
                        # 直接跳出整个循环
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

            # 如果是 break 出来的（手动关闭或登录失败），添加结果并退出
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
        import json
        from datetime import datetime

        result_file = os.path.join(
            DESKTOP_PATH,
            f"doudian_upload_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
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
        await page.wait_for_timeout(5000)
        await browser.close()
        logger.info("浏览器已关闭")


if __name__ == "__main__":
    asyncio.run(run_uploader())