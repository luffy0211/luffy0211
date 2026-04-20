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
    XHS_STATE_FILE, BROWSER_CHANNEL,
    XHS_UPLOAD_EXCEL, XHS_UPLOAD_COLUMNS,
    XHS_GOODS_URL, DESKTOP_PATH,
)

logger = setup_logger("xhs_uploader")


async def is_page_closed(page: Page) -> bool:
    """检查页面是否已关闭"""
    try:
        return page.is_closed()
    except:
        return True


async def upload_main_images(page: Page, image_files: list[str]):
    """上传主图：点击上传区域 → 上传本地图片 → 点击遮挡层触发上传"""
    if await is_page_closed(page):
        return False
    
    logger.info(f"准备上传 {len(image_files)} 张主图...")
    await page.wait_for_timeout(3000)
    
    try:
        # 1. 点击上传区域
        upload_area = page.locator('.upload-trigger, .upload-anchor').first
        await upload_area.wait_for(state="visible", timeout=10000)
        await upload_area.click()
        logger.info("已点击上传区域")
        await page.wait_for_timeout(2000)
        
        # 2. 点击"上传本地图片"
        upload_btn = page.locator('button:has-text("上传本地图片")').first
        await upload_btn.wait_for(state="visible", timeout=10000)
        await upload_btn.click()
        logger.info("已点击上传本地图片")
        await page.wait_for_timeout(2000)
        
        # 3. 点击遮挡层 select-files-wrapper（这是真正触发上传的元素）
        try:
            select_files_wrapper = page.locator('.select-files-wrapper').first
            await select_files_wrapper.wait_for(state="visible", timeout=5000)
            
            async with page.expect_file_chooser(timeout=10000) as fc_info:
                await select_files_wrapper.click()
            
            file_chooser = await fc_info.value
            await file_chooser.set_files(image_files)
            logger.info("图片已选择")
            await page.wait_for_timeout(3000)
        except Exception as e:
            logger.error(f"点击上传区域失败: {e}")
            return False
        
        # 4. 点击确认按钮（使用force=True强制点击，因为可能被遮挡）
        await page.wait_for_timeout(3000)
        
        try:
            confirm_btn = page.locator('.d-drawer-footer button:has-text("确认")').first 
            await confirm_btn.wait_for(state="visible", timeout=5000)
            await confirm_btn.click(force=True)
            logger.info("主图上传完成")
        except Exception as e:
            logger.error(f"点击确认按钮失败: {e}")
            return False
        
        await page.wait_for_timeout(3000)
        return True
    except Exception as e:
        logger.error(f"主图上传失败: {e}")
        return False


async def generate_title_ai(page: Page):
    """智能生成标题（XPath）"""
    if await is_page_closed(page):
        return False
    
    try:
        # XPath: //*[@id="anchor-cell-itemName"]/div[2]/div[1]/button
        generate_btn = page.locator('xpath=//*[@id="anchor-cell-itemName"]/div[2]/div[1]/button')
        await generate_btn.wait_for(state="visible", timeout=10000)
        await generate_btn.click()
        logger.info("已点击智能生成标题")
        await page.wait_for_timeout(4000)
        
        # XPath: //*[@id="anchor-cell-itemName"]/div[2]/div[2]/div/a
        use_btn = page.locator('xpath=//*[@id="anchor-cell-itemName"]/div[2]/div[2]/div/a')
        if await use_btn.is_visible(timeout=5000):
            await use_btn.click()
            logger.info("标题已应用")
            return True
        return False
    except Exception as e:
        logger.warning(f"智能生成标题失败: {e}")
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
        next_btn = page.locator('button:has-text("信息已确认"), button:has-text("下一步")').first
        
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
    """填写商品标题（XPath: //*[@id="anchor-cell-itemName"]/div[2]/div[1]）"""
    if await is_page_closed(page):
        return False
    
    try:
        title_input = page.locator('xpath=//*[@id="anchor-cell-itemName"]/div[2]/div[1]//input').first
        await title_input.wait_for(state="visible", timeout=10000)
        await title_input.click()
        await title_input.fill(title)
        logger.info(f"已填写标题: {title}")
        return True
    except Exception as e:
        logger.error(f"填写标题失败: {e}")
        return False


async def generate_short_title_ai(page: Page):
    """生成导购短标题（XPath: //*[@id="anchor-cell-itemShortTitle"]/div[2]/div/button）"""
    if await is_page_closed(page):
        return False
    
    try:
        short_title_btn = page.locator('xpath=//*[@id="anchor-cell-itemShortTitle"]/div[2]/div/button')
        if await short_title_btn.is_visible(timeout=5000):
            await short_title_btn.click()
            logger.info("导购短标题已生成")
            await page.wait_for_timeout(2000)
            return True
        return False
    except Exception as e:
        logger.warning(f"导购短标题生成失败: {e}")
        return False


async def set_presale_mode(page: Page, days: int = 15):
    """设置预售模式（XPath: //*[@id="anchor-cell-itemDelivery"]/div[2]/div[3]/div/div[2]/div）"""
    if await is_page_closed(page):
        return False
    
    try:
        presale_radio = page.locator('text=全款预售').first
        if await presale_radio.is_visible(timeout=5000):
            await presale_radio.click()
            logger.info("已设置全款预售")
            await page.wait_for_timeout(1000)
        
        # XPath: //*[@id="anchor-cell-itemDelivery"]/div[2]/div[3]/div/div[2]/div
        days_input = page.locator('xpath=//*[@id="anchor-cell-itemDelivery"]/div[2]/div[3]/div/div[2]/div//input')
        if await days_input.is_visible(timeout=5000):
            await days_input.click()
            await days_input.fill(str(days))
            logger.info(f"已设置发货天数: {days}天")
        
        return True
    except Exception as e:
        logger.error(f"设置预售模式失败: {e}")
        return False


async def select_size_spec(page: Page):
    """选择尺码规格：点击含有'尺码'的选项""" 
    if await is_page_closed(page):
        return False
    
    try:
        # 等待页面加载

        await page.wait_for_timeout(2000)
        
       # 点击含有'尺码'的复选框选项 
        size_option_selectors = [
            'xpath=//span[contains(@class,"d-checkbox-label") and contains(text(),"尺码")]',
            'xpath=//div[contains(@class,"d-checkbox")]//span[contains(@class,"d-checkbox-label") and contains(text(),"尺码")]',
            'xpath=//div[contains(@class,"d-checkbox") and contains(.,"尺码")]', 
            'text=尺码',
        ]
        
        size_option_clicked = False
        for selector in size_option_selectors:
            try:
                size_option = page.locator(selector).first
                if await size_option.is_visible(timeout=5000):
                    await size_option.click()
                    logger.info("已选择尺码规格")
                    await page.wait_for_timeout(2000)
                    size_option_clicked = True
                    break
            except:
                continue
        
        if not size_option_clicked:
            logger.error("未找到尺码选项")
            return False
        
        # 等待尺码输入框出现
        size_input = page.locator('xpath=//*[@id="anchor-cell-variantId-5cc0206569bd896d39196455"]//input').first
        await size_input.wait_for(state="visible", timeout=5000)
        logger.info("尺码输入框已加载")
        return True
        
    except Exception as e:
        logger.error(f"选择尺码失败: {e}")
    return False


async def handle_size_template(page: Page, size_format: str = "90-140"):
    """处理尺码信息模板选择或图片识别上传
    
    Args:
        size_format: 尺码格式，如 "90-140"，用于匹配下拉选项
    """
    if await is_page_closed(page):
        return False
    
    try:
        # 检查是否存在尺码信息模板选择器
        template_selector = 'xpath=//div[@id="anchor-尺码信息"]//div[text()="模板"]/ancestor::div[contains(@class,"d-select-wrapper")]'
        template_element = page.locator(template_selector)
        
        if not await template_element.is_visible(timeout=3000):
            logger.info("未找到尺码信息模板选择器，跳过")
            return True
        
        logger.info("找到尺码信息模板选择器")
        
        # 点击模板选择器打开下拉框
        await template_element.click()
        await page.wait_for_timeout(1000)
        
        # 检查是否存在指定格式的选项
        option_xpath = f'(//div[contains(@class,"d-option") and contains(.,"{size_format}")])[1]'
        option = page.locator(f'xpath={option_xpath}')
        
        if await option.is_visible(timeout=2000):
            # 存在选项，直接点击
            await option.click()
            logger.info(f"已选择尺码模板: {size_format}")
            await page.wait_for_timeout(1000)
            return True
        
        # 不存在选项，使用图片识别上传
        logger.info(f"未找到尺码模板 {size_format}，使用图片识别上传")
        
        # 点击"上传图片识别"按钮
        upload_btn = page.locator('xpath=//div[@id="anchor-尺码信息"]//button[contains(.,"上传图片识别")]')
        await upload_btn.click()
        logger.info("已点击上传图片识别")
        await page.wait_for_timeout(2000)
        
        # 在搜索框输入"尺码格式"
        search_input = page.locator('xpath=//div[@class="combine-search"]//input[@placeholder="输入关键词"]')
        await search_input.fill("尺码格式")
        logger.info("已输入搜索关键词: 尺码格式")
        await page.wait_for_timeout(500)
        
        # 点击搜索按钮
        search_btn = page.locator('xpath=//div[@class="combine-search"]//button[contains(@class,"combine-button")]//span[text()=" 搜索 "]')
        await search_btn.click()
        logger.info("已点击搜索")
        await page.wait_for_timeout(2000)
        
        # 选择第一张图片
        image = page.locator('xpath=//div[@class="material-images-wrapper"]//img[@class="card-image"]').first
        await image.click()
        logger.info("已选择图片")
        await page.wait_for_timeout(1000)
        
        # 点击确认按钮（抽屉底部）
        confirm_drawer = page.locator('xpath=//div[@class="d-drawer-footer"]//button[contains(.,"确认")]')
        await confirm_drawer.click()
        logger.info("已点击确认（抽屉）")
        await page.wait_for_timeout(1500)
        
        # 点击确定按钮（弹窗）
        confirm_modal = page.locator('xpath=//div[contains(@class,"d-modal-footer")]//button[normalize-space()="确定"]')
        await confirm_modal.click()
        logger.info("已点击确定（弹窗）")
        await page.wait_for_timeout(1000)
        
        return True
        
    except Exception as e:
        logger.error(f"处理尺码信息模板失败: {e}")
        return False


async def fill_colors(page: Page, colors: list[str]):
    """填写颜色（动态输入框，基础XPath: //*[@id="anchor-cell-variantId-60404e0de85df80001991224"]）"""
    if await is_page_closed(page):
        return False
    
    logger.info(f"准备填写 {len(colors)} 个颜色: {colors}")
    
    for i, color in enumerate(colors):
        if await is_page_closed(page):
            return False
        
        try:
            # 查找所有颜色输入框，取最后一个（最新生成的）
            color_inputs = page.locator('xpath=//*[@id="anchor-cell-variantId-60404e0de85df80001991224"]//input')
            count = await color_inputs.count()
            
            if count > 0:
                color_input = color_inputs.nth(count - 1)
                await color_input.wait_for(state="visible", timeout=3000)
                await color_input.click()
                await page.keyboard.type(color, delay=80)
                await page.keyboard.press('Enter')
                logger.info(f"已填写颜色 {i+1}: {color}")
                await page.wait_for_timeout(1500)
            else:
                logger.warning(f"未找到颜色输入框 {i+1}")
        except Exception as e:
            logger.warning(f"填写颜色 {i+1} 失败: {e}")
    
    return True


async def upload_spec_images(page: Page, image_paths: list[str]):
    """批量上传规格图（使用XPath）"""
    if await is_page_closed(page):
        return False
    
    try:
        # 1. 点击批量上传规格图（使用.first避免多个匹配）
        batch_upload_btn = page.locator('text=批量上传规格图').first
        await batch_upload_btn.wait_for(state="visible", timeout=10000)
        await batch_upload_btn.click()
        logger.info("已点击批量上传规格图")
        await page.wait_for_timeout(1500)
        
        # 2. 点击上传本地图片
        local_upload_btn = page.locator('button:has-text("上传本地图片")').first
        await local_upload_btn.wait_for(state="visible", timeout=10000)
        await local_upload_btn.click()
        logger.info("已点击上传本地图片")
        await page.wait_for_timeout(1500)
        
        # 3. 点击上传区域（XPath: /html/body/div[24]/div/div[2]/div/div[1]/div[1]/div）
        upload_trigger = page.locator('.select-files-wrapper').first
        await upload_trigger.wait_for(state="visible", timeout=10000)
        
        async with page.expect_file_chooser(timeout=15000) as fc_info:
            await upload_trigger.click()
        
        file_chooser = await fc_info.value
        await file_chooser.set_files(image_paths)
        logger.info(f"规格图已选择 {len(image_paths)} 张")
        await page.wait_for_timeout(3000)
        
        # 4. 点击确定（XPath: /html/body/div[24]/div/div[3]/div/button[2]）
        await page.wait_for_timeout(3000)
        
        try:
            confirm_btn = page.locator('.d-drawer-footer button:has-text("确认")').first 
            await confirm_btn.wait_for(state="visible", timeout=5000)
            await confirm_btn.click(force=True)
            logger.info("主图上传完成")
        except Exception as e:
            logger.error(f"点击确认按钮失败: {e}")
            return False
        await page.wait_for_timeout(3000)
        return True
    except Exception as e:
        logger.error(f"上传规格图失败: {e}")
        return False


async def fill_sizes(page: Page, sizes: list[str]):
    """填写尺码（动态输入框，与颜色输入框类似，填写一个会弹出下一个）"""
    if await is_page_closed(page):
        return False
    
    logger.info(f"准备填写 {len(sizes)} 个尺码: {sizes}")
    
    for i, size in enumerate(sizes):
        if await is_page_closed(page):
            return False
        
        try:
            # 使用精确的 XPath 定位尺码输入框
            size_input_selector = 'xpath=//div[contains(@class,"variant-info") and contains(.,"尺码")]//input[@placeholder="请选择或输入规格值"]'
            
            size_inputs = page.locator(size_input_selector)
            count = await size_inputs.count()
            
            if count > 0:
                # 取最后一个输入框（最新生成的）
                size_input = size_inputs.nth(count - 1)
                await size_input.wait_for(state="visible", timeout=3000)
                await size_input.click()
                await page.keyboard.type(size, delay=80)
                await page.keyboard.press('Enter')
                logger.info(f"已填写尺码 {i+1}: {size}")
                await page.wait_for_timeout(1500)
            else:
                logger.warning(f"未找到尺码输入框 {i+1}")
        except Exception as e:
            logger.warning(f"填写尺码 {i+1} 失败: {e}")
    
    return True


async def fill_product_attributes(page: Page, item: dict):
    """填写商品属性（关键属性和其他属性）
    
    Args:
        item: 商品数据字典，包含以下字段：
            - style (F列): 风格
            - season (H列): 适应季节
            - material_composition (I列): 材质成分（可能多个，空格分割，只提取文字部分）
            - fabric (J列): 面料
            - safety_level (K列): 安全等级
    """
    if await is_page_closed(page):
        return False
    
    logger.info("开始填写商品属性...")
    
    # 属性映射：Excel列 -> 属性名称
    attributes = {
        "style": "风格",
        "season": "适应季节", 
        "material_composition": "材质成分",
        "fabric": "面料",
        "safety_level": "安全等级"
    }
    
    for key, attr_name in attributes.items():
        value = item.get(key)
        if not value:
            continue
        
        try:
            # 构造 XPath 定位输入框
            xpath = f'(//span[normalize-space()="{attr_name}"]/following::div[@data-v-e28b1bfa and @tabindex="1"])[1]'
            input_field = page.locator(f'xpath={xpath}')
            
            if await input_field.is_visible(timeout=3000):
                # 材质成分可能有多个值（空格分割），只提取文字部分
                if key == "material_composition":
                    materials = [m.strip() for m in str(value).split() if m.strip()]
                    for material in materials:
                        # 只提取文字部分，去除数字、百分号和括号
                        material_text = re.sub(r'[\d%()（）]+', '', material).strip() 
                        if not material_text:
                            continue
                        
                        await input_field.click()
                        await page.wait_for_timeout(500)
                        await page.keyboard.type(material_text, delay=50)
                        await page.wait_for_timeout(1200)
                        
                        # 检查是否显示"暂无数据"
                        no_data_xpath = "//div[contains(@class,'d-popover') and contains(@style,'transform')]//div[text()='暂无数据']"
                        no_data = page.locator(f'xpath={no_data_xpath}')
                        
                        if await no_data.is_visible(timeout=800):
                            # 暂无数据，清空并输入"其他"
                            logger.info(f"{attr_name} 暂无数据，改为填写'其他'")
                            await input_field.click()
                            await page.keyboard.press('Control+A')
                            await page.keyboard.press('Backspace')
                            await page.wait_for_timeout(300)
                            await page.keyboard.type("其他", delay=50)
                            await page.wait_for_timeout(1000)
                            
                            # 尝试点击所有"其他"选项，直到成功
                            other_options_xpath = "//div[contains(@style,'translate3d') and contains(@class,'d-popover')]//span[normalize-space()='其他']"
                            other_options = page.locator(f'xpath={other_options_xpath}')
                            count = await other_options.count()
                            
                            for i in range(count):
                                try:
                                    await other_options.nth(i).click(timeout=1000)
                                    logger.info(f"已填写{attr_name}: 其他 (尝试第{i+1}个)")
                                    await page.wait_for_timeout(500)
                                    break
                                except:
                                    continue
                        else:
                            # 有数据，直接点击第一个匹配的选项
                            option_xpath = f"//div[contains(@style,'translate3d') and contains(@class,'d-popover')]//span[normalize-space()='{material_text}']"
                            option = page.locator(f'xpath={option_xpath}').first
                            await option.click()
                            logger.info(f"已填写{attr_name}: {material_text}")
                            await page.wait_for_timeout(500)
                else:
                    # 其他属性直接输入
                    await input_field.click()
                    await page.wait_for_timeout(500)
                    await page.keyboard.type(str(value), delay=50)
                    await page.wait_for_timeout(1200)
                    
                    # 检查是否显示"暂无数据"
                    no_data_xpath = "//div[contains(@class,'d-popover') and contains(@style,'transform')]//div[text()='暂无数据']"
                    no_data = page.locator(f'xpath={no_data_xpath}')
                    
                    if await no_data.is_visible(timeout=800):
                        # 暂无数据，清空并输入"其他"
                        logger.info(f"{attr_name} 暂无数据，改为填写'其他'")
                        await input_field.click()
                        await page.keyboard.press('Control+A')
                        await page.keyboard.press('Backspace')
                        await page.wait_for_timeout(300)
                        await page.keyboard.type("其他", delay=50)
                        await page.wait_for_timeout(1000)
                        
                        # 尝试点击所有"其他"选项，直到成功
                        other_options_xpath = "//div[contains(@style,'translate3d') and contains(@class,'d-popover')]//span[normalize-space()='其他']"
                        other_options = page.locator(f'xpath={other_options_xpath}')
                        count = await other_options.count()
                        
                        for i in range(count):
                            try:
                                await other_options.nth(i).click(timeout=1000)
                                logger.info(f"已填写{attr_name}: 其他 (尝试第{i+1}个)")
                                await page.wait_for_timeout(500)
                                break
                            except:
                                continue
                    else:
                        # 有数据，直接点击第一个匹配的选项
                        option_xpath = f"//div[contains(@style,'translate3d') and contains(@class,'d-popover')]//span[normalize-space()='{value}']"
                        option = page.locator(f'xpath={option_xpath}').first
                        await option.click()
                        logger.info(f"已填写{attr_name}: {value}")
                        await page.wait_for_timeout(500)
            else:
                logger.warning(f"未找到属性输入框: {attr_name}")
        except Exception as e:
            logger.warning(f"填写属性 {attr_name} 失败: {e}")
    
    return True


async def batch_fill_price_stock(page: Page, sale_price: str, market_price: str, stock: int = 10):
    """批量填写价格库存（使用XPath）"""
    if await is_page_closed(page):
        return False
    
    try:
        batch_btn = page.locator('button:has-text("批量填写")').first
        await batch_btn.wait_for(state="visible", timeout=10000)
        await batch_btn.click()
        logger.info("已打开批量填写弹窗")
        await page.wait_for_timeout(1000)
        
        # 售价（XPath: //*[@id="sku-batch-setting"]/div[2]/div[2]/div/div/div[1]/input）
        sale_price_input = page.locator('xpath=//*[@id="sku-batch-setting"]/div[2]/div[2]/div/div/div[1]/input')
        if await sale_price_input.is_visible(timeout=5000):
            await sale_price_input.click()
            await sale_price_input.fill(sale_price)
            logger.info(f"已填写售价: {sale_price}")
        
        # 库存（XPath: //*[@id="sku-batch-setting"]/div[2]/div[3]/div/div/div[1]/input）
        stock_input = page.locator('xpath=//*[@id="sku-batch-setting"]/div[2]/div[3]/div/div/div[1]/input')
        if await stock_input.is_visible(timeout=5000):
            await stock_input.click()
            await stock_input.fill(str(stock))
            logger.info(f"已填写库存: {stock}")
        
        # 市场价（XPath: //*[@id="sku-batch-setting"]/div[2]/div[4]/div/div/div[1]/input）
        market_price_input = page.locator('xpath=//*[@id="sku-batch-setting"]/div[2]/div[4]/div/div/div[1]/input')
        if await market_price_input.is_visible(timeout=5000):
            await market_price_input.click()
            await market_price_input.fill(market_price)
            logger.info(f"已填写市场价: {market_price}")
        
        # 点击确定按钮（使用更灵活的选择器）
        confirm_btn_selectors = [
            '.d-drawer-footer button:has-text("确定")',
            'button:has-text("确定")',
            'xpath=//button[contains(text(),"确定")]',
        ]
        
        confirm_clicked = False
        for selector in confirm_btn_selectors:
            try:
                confirm_btn = page.locator(selector).first
                if await confirm_btn.is_visible(timeout=3000):
                    await confirm_btn.click()
                    logger.info("价格库存填写完成")
                    confirm_clicked = True
                    break
            except:
                continue
        
        if not confirm_clicked:
            logger.warning("未找到确定按钮，尝试按 Enter 键")
            await page.keyboard.press('Enter')
        
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
    logger.info(f"\n--- 正在处理第 {index} 条 ---")
    
    image_path = item.get("image_path")
    title = item.get("title")
    color = item.get("color")
    sale_price = item.get("sale_price")
    price = item.get("price")
    color_image_paths = item.get("color_image_paths", "")
    sizes = item.get("sizes", "")
    
    logger.info(f"标题: {title}")
    
    if await is_page_closed(page):
        return False
    
    # 1. 上传主图
    image_files = get_images_from_folder(str(image_path)) if image_path else []
    if image_files:
        await upload_main_images(page, image_files)
    
    # 2. 智能生成标题
    title_generated = await generate_title_ai(page)
    
    # 3. 等待类目加载
    await wait_category_ready(page)
    
    # 4. 点击下一步
    await click_confirm_next(page)
    
    # 5. 填写标题（如果智能生成失败）
    if not title_generated and title:
        await fill_title_manual(page, title)
    
    # 6. 生成导购短标题
    await generate_short_title_ai(page)
    
    # 7. 设置预售
    await set_presale_mode(page, 15)
    
    # 8. 选择尺码规格
    await select_size_spec(page)
    
    # 9. 处理尺码信息模板（如果存在）
    await handle_size_template(page, "90-140")
    
    # 10. 填写颜色
    if color:
        colors = [c.strip() for c in str(color).split() if c.strip()]
        await fill_colors(page, colors)
    
    # 11. 上传规格图
    if color_image_paths:
        spec_image_paths = [p.strip() for p in str(color_image_paths).split() if p.strip()]
        if spec_image_paths:
            all_spec_images = []
            for path in spec_image_paths:
                images = get_images_from_folder(path)
                all_spec_images.extend(images)
            
            if all_spec_images:
                await upload_spec_images(page, all_spec_images)
    
    # 12. 填写尺码
    if sizes:
        size_list = clean_sizes(str(sizes))
        if size_list:
            await fill_sizes(page, size_list)
    
    # 12. 填写商品属性（风格、季节、材质成分、面料、安全等级）
    await fill_product_attributes(page, item)
    
    # 14. 批量填写价格库存
    if sale_price and price:
        market_price = str(round(float(price) * 3, 2))
        await batch_fill_price_stock(page, str(sale_price), market_price, 10)
    
    # 15. 提交商品
    try:
        submit_btn = page.locator('xpath=//div[@class="action-bar"]//button[normalize-space()="提交商品"]')
        await submit_btn.click()
        logger.info("已点击提交商品")
        await page.wait_for_timeout(3000)
    except Exception as e:
        logger.error(f"提交商品失败: {e}")
    
    await page.wait_for_timeout(2000)
    logger.info(f"第 {index} 条处理完成")
    return True


async def run_uploader():
    """批量上架"""
    if not os.path.exists(XHS_STATE_FILE):
        logger.error(f"未找到 {XHS_STATE_FILE}，请先登录")
        return
    
    data = read_upload_data(XHS_UPLOAD_EXCEL, XHS_UPLOAD_COLUMNS)
    if not data:
        logger.error("无可用数据")
        return
    
    logger.info(f"共 {len(data)} 条商品待上架")
    
    results = []
    
    async with async_playwright() as p:
        browser = await launch_browser(p, channel=BROWSER_CHANNEL)
        context = await create_context(browser, state_file=XHS_STATE_FILE, no_viewport=True)
        page = await context.new_page()
        
        for i, item in enumerate(data, 1):
            try:
                await page.goto(XHS_GOODS_URL, wait_until="domcontentloaded")
                await asyncio.sleep(3)
                await handle_popups(page)
                
                success = await process_single_item(page, item, i)
                results.append({
                    "index": i,
                    "title": item.get("title", ""),
                    "success": success
                })
            except Exception as e:
                logger.error(f"处理第 {i} 条出错: {e}")
                results.append({
                    "index": i,
                    "title": item.get("title", ""),
                    "success": False,
                    "error": str(e)
                })
            
            if i < len(data):
                await page.wait_for_timeout(2000)
        
        logger.info(f"\n全部完成！共处理 {len(data)} 条")
        
        # 生成 JSON 结果文件
        import json
        from datetime import datetime
        
        result_file = os.path.join(DESKTOP_PATH, f"xhs_upload_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump({
                "total": len(data),
                "success": sum(1 for r in results if r.get("success")),
                "failed": sum(1 for r in results if not r.get("success")),
                "results": results
            }, f, ensure_ascii=False, indent=2)
        
        logger.info(f"结果已保存到: {result_file}")
        
        # 关闭浏览器
        await browser.close()
        logger.info("浏览器已关闭")


if __name__ == "__main__":
    asyncio.run(run_uploader())