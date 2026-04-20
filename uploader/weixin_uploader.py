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
    WEIXIN_STATE_FILE, BROWSER_CHANNEL,
    UPLOAD_EXCEL, UPLOAD_COLUMNS,
    WEIXIN_GOODS_URL, WEIXIN_MICRO_APP,
)

logger = setup_logger("uploader")


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
                        input.click();
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
                    // 先点击输入框
                    input.click();
                    // 然后输入内容
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


async def wait_for_recommend_reason(page, max_wait: int = 10):
    """等待推荐理由出现"""
    for i in range(max_wait):
        found = await page.evaluate(_shadow_js("""
            const divs = shadowRoot.querySelectorAll('div, [class*="recommend"]');
            for (const el of divs) {
                if ((el.textContent || '').includes('推荐理由')) return { success: true };
            }
            return { success: false };
        """))
        if found.get("success"):
            logger.info("推荐理由已出现")
            return True
        logger.info(f"等待推荐理由... ({i+1}/{max_wait})")
        await page.wait_for_timeout(2000)
    logger.info("未找到推荐理由，继续执行")
    return False


async def click_next_button(page):
    """点击下一步按钮"""
    await page.wait_for_timeout(2000)
    await wait_for_recommend_reason(page)

    try:
        # 先在 Python 侧轮询按钮是否可用
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


async def select_style(page, style_text: str):
    """选择风格下拉框，无结果时输入其他"""
    try:
        # 第一步：点击下拉框
        await page.evaluate(_shadow_js("""
            const dropdown = shadowRoot.querySelector('input[placeholder*="风格"]');
            if (dropdown) dropdown.click();
        """))

        await page.wait_for_timeout(800)

        # 第二步：尝试选择匹配的选项
        result = await page.evaluate(_shadow_js_with_arg("""
            const options = shadowRoot.querySelectorAll('.weui-desktop-dropdown__list-ele');
            for (const opt of options) {
                const text = opt.textContent || opt.innerText || '';
                if (text.includes(arg)) {
                    opt.click();
                    return { success: true, selected: text.trim(), hasResult: true };
                }
            }
            // 没有找到匹配项，检查是否有"其他"选项
            for (const opt of options) {
                const text = opt.textContent || opt.innerText || '';
                if (text.includes('其他')) {
                    opt.click();
                    return { success: true, selected: '其他', hasResult: false };
                }
            }
            // 如果有选项但没有"其他"，选择第一个
            if (options.length > 0) {
                options[0].click();
                return { success: true, selected: 'first_option', hasResult: false };
            }
            return { success: false, reason: 'no options found' };
        """), style_text)

        if result.get("success"):
            if result.get("hasResult"):
                logger.info(f"风格已选择: {result.get('selected', style_text)}")
            else:
                logger.info(f"风格无搜索结果，已选择: {result.get('selected', '其他')}")
        else:
            logger.warning(f"风格选择失败: {result.get('reason')}")
    except Exception as e:
        logger.error(f"风格选择异常: {e}")


async def select_safety_level(page, safety_level: str):
    """选择安全等级，为空时输入其他"""
    try:
        await page.wait_for_timeout(1000)
        
        # 如果安全等级为空，使用"其他"
        if not safety_level or str(safety_level).strip() == "":
            safety_level = "其他"
            logger.info("安全等级为空，将选择'其他'")
        
        # 第一步：点击安全等级下拉框
        await page.evaluate(_shadow_js("""
            const inputs = shadowRoot.querySelectorAll('input[placeholder*="安全"], input[placeholder*="等级"]');
            for (const input of inputs) {
                const placeholder = input.placeholder || '';
                if (placeholder.includes('安全') || placeholder.includes('等级')) {
                    input.click();
                    break;
                }
            }
        """))

        await page.wait_for_timeout(800)

        # 第二步：选择选项
        result = await page.evaluate(_shadow_js_with_arg("""
            const options = shadowRoot.querySelectorAll('.weui-desktop-dropdown__list-ele');
            for (const opt of options) {
                const text = opt.textContent || opt.innerText || '';
                if (text.includes(arg)) {
                    opt.click();
                    return { success: true, selected: text.trim() };
                }
            }
            // 如果没找到，选择第一个
            if (options.length > 0) {
                options[0].click();
                return { success: true, selected: 'first_option' };
            }
            return { success: false, reason: 'no options found' };
        """), safety_level)

        if result.get("success"):
            logger.info(f"安全等级已选择: {result.get('selected', safety_level)}")
        else:
            logger.warning(f"安全等级选择失败: {result.get('reason')}")
    except Exception as e:
        logger.error(f"安全等级选择异常: {e}")


async def fill_material_percentage(page, percentage: str = "100"):
    """填写面料材质成分含量（%）"""
    try:
        await page.wait_for_timeout(1500)
        
        result = await page.evaluate(_shadow_js_with_arg("""
            // 扩大搜索范围，查找所有输入框
            const allInputs = shadowRoot.querySelectorAll('input[type="text"], input[type="number"], input:not([type="radio"]):not([type="checkbox"])');
            
            for (const input of allInputs) {
                const placeholder = input.placeholder || '';
                const value = input.value || '';
                
                // 获取多层父元素的文本
                let parentText = '';
                let parent = input.parentElement;
                let level = 0;
                while (parent && level < 3) {
                    parentText += ' ' + (parent.textContent || '');
                    parent = parent.parentElement;
                    level++;
                }
                
                // 匹配多种可能的文本（包括"含量"、"%"、"百分比"等）
                if (placeholder.includes('%') || placeholder.includes('含量') || placeholder.includes('成分') || placeholder.includes('百分比') ||
                    parentText.includes('成分含量') || parentText.includes('材质成分') || parentText.includes('%') || 
                    parentText.includes('面料成分') || parentText.includes('含量(%)') || parentText.includes('百分比')) {
                    
                    // 排除已经有值的输入框（可能是其他字段）
                    if (value && value !== '' && value !== '0') {
                        continue;
                    }
                    
                    input.click();
                    input.focus();
                    return { success: true, placeholder: placeholder, parentText: parentText.substring(0, 100) };
                }
            }
            return { success: false, reason: 'material percentage input not found', inputCount: allInputs.length };
        """), percentage)
        
        if result.get("success"):
            await page.wait_for_timeout(300)
            # 先清空可能存在的值
            await page.keyboard.press('Control+A')
            await page.keyboard.press('Backspace')
            await page.wait_for_timeout(100)
            # 输入新值
            await page.keyboard.type(percentage, delay=80)
            logger.info(f"已填写面料材质成分含量: {percentage}% (placeholder: {result.get('placeholder', 'N/A')})")
        else:
            logger.warning(f"面料材质成分含量填写失败: {result.get('reason')} (找到 {result.get('inputCount', 0)} 个输入框)")
    except Exception as e:
        logger.error(f"面料材质成分含量填写异常: {e}")


async def select_age_range(page):
    """选择使用年龄为全选（多选复选框）"""
    try:
        await page.wait_for_timeout(1000)
        
        # 第一步：点击适用年龄下拉框展开
        result1 = await page.evaluate(_shadow_js("""
            // 查找所有包含"适用年龄"文本的 dt 元素
            const allDts = shadowRoot.querySelectorAll('dt.weui-desktop-form__dropdown__dt');
            
            for (const dt of allDts) {
                const text = dt.textContent || dt.innerText || '';
                if (text.includes('适用年龄') || text.includes('请设置适用年龄')) {
                    dt.click();
                    return { success: true, text: text.trim() };
                }
            }
            
            return { success: false, reason: 'dropdown trigger not found' };
        """))
        
        if result1.get("success"):
            logger.info(f"已点击适用年龄下拉框 (文本: {result1.get('text', 'N/A')})")
        else:
            logger.warning(f"适用年龄下拉框点击失败: {result1.get('reason')}")
            return

        # 增加等待时间，确保下拉框完全展开
        await page.wait_for_timeout(3000)

        # 第二步：查找并点击"全选"复选框
        result2 = await page.evaluate(_shadow_js("""
            // 查找所有复选框
            const allCheckboxes = shadowRoot.querySelectorAll('input[type="checkbox"]');
            console.log('Total checkboxes found:', allCheckboxes.length);
            
            for (let i = 0; i < allCheckboxes.length; i++) {
                const checkbox = allCheckboxes[i];
                const parent = checkbox.closest('label');
                if (parent) {
                    const text = (parent.textContent || parent.innerText || '').trim();
                    console.log(`Checkbox ${i}: text="${text}", checking="${checkbox.getAttribute('checking')}", checked=${checkbox.checked}`);
                    
                    // 匹配"全选"
                    if (text === '全选' || text.includes('全选')) {
                        const checkingAttr = checkbox.getAttribute('checking');
                        const isChecked = checkbox.checked || checkingAttr === 'checking';
                        
                        console.log('Found 全选 checkbox, will click it');
                        // 无论是否已勾选，都点击一次（可能需要触发事件）
                        checkbox.click();
                        
                        return { 
                            success: true, 
                            selected: '全选', 
                            wasChecked: isChecked,
                            checkingAttr: checkingAttr
                        };
                    }
                }
            }
            
            return { success: false, reason: 'checkbox not found', totalCheckboxes: allCheckboxes.length };
        """))

        if result2.get("success"):
            logger.info(f"已点击使用年龄'全选' (之前状态: {'已勾选' if result2.get('wasChecked') else '未勾选'}, checking={result2.get('checkingAttr')})")
            # 点击后等待一下，确保状态更新
            await page.wait_for_timeout(1000)
        else:
            logger.warning(f"使用年龄选择失败: {result2.get('reason')} (找到 {result2.get('totalCheckboxes', 0)} 个复选框)")
    except Exception as e:
        logger.error(f"使用年龄选择异常: {e}")



    """点击创建新规格"""
async def click_create_spec(page):
    try:
        # 增加等待时间确保页面加载完成
        await page.wait_for_timeout(2000)
        
        # 尝试点击创建新规格
        result = await page.evaluate(_shadow_js("""
            // 方法1：通过完整路径查找 - 从规格和库存价格开始
            const goodsSaleParams = shadowRoot.querySelector('.goods-sale-params');
            if (goodsSaleParams) {
                const boxContent = goodsSaleParams.querySelector('.box_content');
                if (boxContent) {
                    const specDiv = boxContent.querySelector('[data-eleid="sale_attr"]');
                    if (specDiv) {
                        const blockContent = specDiv.querySelector('.block_content');
                        if (blockContent) {
                            const createSpec = blockContent.querySelector('.flex.items-center.w-fit.cursor-pointer');
                            if (createSpec) {
                                console.log('Found create spec by full path');
                                createSpec.click();
                                return { success: true, method: 'full_path' };
                            }
                        }
                    }
                }
            }
            
            // 方法2：直接通过文本内容查找
            const elements = shadowRoot.querySelectorAll('div');
            for (const el of elements) {
                const text = el.textContent || el.innerText || '';
                if (text.includes('创建新规格')) {
                    console.log('Found create spec by text:', text);
                    el.click();
                    return { success: true, method: 'text' };
                }
            }
            
            // 方法3：通过图片+文本组合查找
            const imgElements = shadowRoot.querySelectorAll('img[src*="Icons_Outlined_add2.svg"]');
            for (const img of imgElements) {
                const nextSibling = img.nextElementSibling;
                if (nextSibling && (nextSibling.textContent || '').includes('创建新规格')) {
                    console.log('Found create spec by image+text');
                    nextSibling.click();
                    return { success: true, method: 'image+text' };
                }
            }
            
            return { success: false, reason: 'create spec not found' };
        """))

        if result.get("success"):
            logger.info(f"已点击创建新规格 (方法: {result.get('method')})")
        else:
            logger.warning(f"创建新规格点击失败: {result.get('reason')}")
    except Exception as e:
        logger.error(f"创建新规格点击异常: {e}")


async def select_size_color(page):
    """点击尺码下拉框并选择颜色"""
    try:
        # 第一步：点击尺码下拉框
        await page.evaluate(_shadow_js("""
            // 查找包含尺码文本的下拉框
            const size_dts = shadowRoot.querySelectorAll('dt.weui-desktop-form__dropdown__dt');
            let size_dt = null;
            
            for (const dt of size_dts) {
                const text = dt.textContent || dt.innerText || '';
                if (text.includes('尺码')) {
                    size_dt = dt;
                    break;
                }
            }
            
            // 备用：查找包含尺码值的下拉框
            if (!size_dt) {
                const size_values = shadowRoot.querySelectorAll('.weui-desktop-form__dropdown__value');
                for (const value of size_values) {
                    if ((value.textContent || '').includes('尺码')) {
                        size_dt = value.closest('dt.weui-desktop-form__dropdown__dt');
                        break;
                    }
                }
            }
            
            if (size_dt) size_dt.click();
        """))

        await page.wait_for_timeout(800)

        # 第二步：选择颜色选项
        result = await page.evaluate(_shadow_js("""
            const options = shadowRoot.querySelectorAll('.weui-desktop-dropdown__list-ele');
            for (const opt of options) {
                const text = opt.textContent || opt.innerText || '';
                if (text.includes('颜色')) {
                    opt.click();
                    return { success: true };
                }
            }
            return { success: false, reason: 'color option not found' };
        """))

        if result.get("success"):
            logger.info("已选择颜色选项")
        else:
            logger.warning(f"颜色选择失败: {result.get('reason')}")
    except Exception as e:
        logger.error(f"颜色选择异常: {e}")


async def fill_colors(page, color_text: str):
    """填写颜色值，支持多个颜色（模拟键盘输入）"""
    try:
        # 分割颜色（空格分隔）
        colors = [c.strip() for c in color_text.split(' ') if c.strip()]
        if not colors:
            logger.warning("无有效颜色数据")
            return
        
        logger.info(f"准备填写 {len(colors)} 个颜色: {colors}")
        
        # 等待颜色输入框出现
        await page.wait_for_timeout(1000)
        
        # 逐个填写颜色
        for i, color in enumerate(colors):
            logger.info(f"正在填写颜色 {i+1}: {color}")
            
            # 使用 Playwright 的 keyboard.type 方法模拟真实键盘输入
            result = await page.evaluate(_shadow_js_with_arg(f'''
                const goodsSaleParams = shadowRoot.querySelector('.goods-sale-params');
                let inputs = [];
                
                if (goodsSaleParams) {{
                    inputs = goodsSaleParams.querySelectorAll('input[placeholder*="请输入颜色"]');
                }}
                
                if (inputs.length === 0) {{
                    inputs = shadowRoot.querySelectorAll('input[placeholder*="请输入颜色"]');
                }}
                
                if (inputs[{i}]) {{
                    inputs[{i}].click();
                    inputs[{i}].focus();
                    return {{ success: true, index: {i}, inputCount: inputs.length }};
                }}
                return {{ success: false, reason: 'input not found', inputCount: inputs.length }};
            '''), color)
            
            if result.get("success"):
                # 等待输入框获得焦点
                await page.wait_for_timeout(200)
                
                # 使用 keyboard.type 模拟真实键盘输入
                await page.keyboard.type(color, delay=80)
                
                # 按下回车键触发输入完成
                await page.keyboard.press('Enter')
                
                logger.info(f"已填写颜色 {i+1}: {color} (当前输入框数量: {result.get('inputCount', 0)})")
                
                # 如果还有下一个颜色，等待新输入框生成
                if i < len(colors) - 1:
                    logger.info("等待新的颜色输入框生成...")
                    await page.wait_for_timeout(1200)
            else:
                logger.warning(f"颜色 {i+1} 填写失败: {result.get('reason')} (当前输入框数量: {result.get('inputCount', 0)})")
                await page.wait_for_timeout(1000)
                
    except Exception as e:
        logger.error(f"填写颜色异常: {e}")


async def upload_color_images(page, color_image_paths: str, color_text: str):
    """上传颜色对应图片"""
    try:
        # 分割颜色和图片路径
        colors = [c.strip() for c in color_text.split(' ') if c.strip()]
        image_paths = [p.strip() for p in color_image_paths.split(' ') if p.strip()]
        
        if not colors:
            logger.warning("无颜色数据")
            return
        
        if not image_paths:
            logger.warning("无颜色图片路径")
            return
        
        logger.info(f"准备上传 {len(colors)} 个颜色的图片")
        logger.info(f"颜色列表: {colors}")
        logger.info(f"图片路径列表: {image_paths}")
        
        # 确保颜色和图片路径数量匹配
        if len(colors) > len(image_paths):
            logger.warning(f"颜色数量 ({len(colors)}) 大于图片路径数量 ({len(image_paths)})")
            # 重复使用最后一个图片路径
            while len(image_paths) < len(colors):
                image_paths.append(image_paths[-1])
            logger.info(f"调整后图片路径列表: {image_paths}")
        
        # 等待页面就绪
        await page.wait_for_timeout(3000)
        
        # 逐个上传颜色图片
        for i, color in enumerate(colors):
            image_path = image_paths[i]
            logger.info(f"正在上传 {color} 的图片: {image_path}")
            
            # 获取该路径下的所有图片
            all_images = get_images_from_folder(image_path)
            if not all_images:
                logger.warning(f"路径 {image_path} 下未找到图片")
                continue
            
            # 确保图片数量足够
            if i >= len(all_images):
                logger.warning(f"{color} 没有对应的图片 (需要第 {i+1} 张，只有 {len(all_images)} 张)")
                continue
            
            # 获取当前颜色对应的图片
            target_image = all_images[i]
            logger.info(f"选择 {color} 对应的图片: {target_image}")
            
            # 查找并点击颜色对应的上传按钮
            try:
                # 尝试多种定位方式
                upload_success = False
                
                # 方法1：通过goods-content-row找到对应索引的上传按钮
                try:
                    async with page.expect_file_chooser(timeout=10000) as fc_info:
                        result = await page.evaluate(_shadow_js_with_arg('''
                            const goodsSaleParams = shadowRoot.querySelector('.goods-sale-params');
                            if (goodsSaleParams) {
                                // 查找所有颜色行
                                const colorRows = goodsSaleParams.querySelectorAll('.goods-content-row > div');
                                console.log('Found color rows:', colorRows.length);
                                
                                if (colorRows[arg]) {
                                    // 在该行中查找上传按钮
                                    const uploadIcon = colorRows[arg].querySelector('.property_entry_item_upload_icon.content');
                                    if (uploadIcon) {
                                        console.log('Found upload icon for color row:', arg);
                                        uploadIcon.click();
                                        return { success: true, method: 'color_row', rowIndex: arg };
                                    }
                                }
                            }
                            return { success: false, reason: 'upload icon not found in color row' };
                        '''), i)

                        if result.get('success'):
                            logger.info(f"成功点击第 {result.get('rowIndex')} 行的上传按钮")
                            
                            # 上传图片
                            file_chooser = await fc_info.value
                            await file_chooser.set_files([target_image])
                            logger.info(f"已上传 {color} 的图片: {target_image}")
                            upload_success = True
                except Exception as e:
                    logger.warning(f"方法1上传失败: {e}")
                
                # 方法2：直接查找所有上传按钮并点击对应索引
                if not upload_success:
                    try:
                        async with page.expect_file_chooser(timeout=10000) as fc_info:
                            result = await page.evaluate(_shadow_js_with_arg('''
                                const goodsSaleParams = shadowRoot.querySelector('.goods-sale-params');
                                if (goodsSaleParams) {
                                    // 查找所有上传图标
                                    const uploadIcons = goodsSaleParams.querySelectorAll('.property_entry_item_upload_icon.content');
                                    console.log('Found upload icons:', uploadIcons.length);
                                    
                                    if (uploadIcons[arg]) {
                                        console.log('Clicking upload icon:', arg);
                                        uploadIcons[arg].click();
                                        return { success: true, method: 'direct_index', buttonIndex: arg };
                                    }
                                }
                                return { success: false, reason: 'upload icon not found' };
                            '''), i)

                        if result.get('success'):
                            logger.info(f"成功点击第 {result.get('buttonIndex')} 个上传按钮")
                            
                            # 上传图片
                            file_chooser = await fc_info.value
                            await file_chooser.set_files([target_image])
                            logger.info(f"已上传 {color} 的图片: {target_image}")
                            upload_success = True
                    except Exception as e:
                        logger.warning(f"方法2上传失败: {e}")
                    
                # 方法3：通过输入框找到对应的上传按钮
                if not upload_success:
                    try:
                        async with page.expect_file_chooser(timeout=10000) as fc_info:
                            result = await page.evaluate(_shadow_js_with_arg('''
                                const goodsSaleParams = shadowRoot.querySelector('.goods-sale-params');
                                if (goodsSaleParams) {
                                    // 查找所有颜色输入框
                                    const colorInputs = goodsSaleParams.querySelectorAll('input[placeholder*="请输入颜色"]');
                                    console.log('Found color inputs:', colorInputs.length);
                                    
                                    if (colorInputs[arg]) {
                                        // 找到该输入框的父容器
                                        let currentElement = colorInputs[arg].closest('.style_width');
                                        if (currentElement) {
                                            // 找到上传按钮
                                            const uploadIcon = currentElement.querySelector('.property_entry_item_upload_icon.content');
                                            if (uploadIcon) {
                                                console.log('Found upload icon near input:', arg);
                                                uploadIcon.click();
                                                return { success: true, method: 'input_nearby' };
                                            }
                                        }
                                    }
                                }
                                return { success: false, reason: 'upload icon not found near input' };
                            '''), i)

                        if result.get('success'):
                            logger.info(f"成功点击 {color} 输入框附近的上传按钮")
                            
                            # 上传图片
                            file_chooser = await fc_info.value
                            await file_chooser.set_files([target_image])
                            logger.info(f"已上传 {color} 的图片: {target_image}")
                            upload_success = True
                    except Exception as e:
                        logger.warning(f"方法3上传失败: {e}")
                    
                if not upload_success:
                    logger.error(f"无法上传 {color} 的图片")
                    
            except Exception as e:
                logger.error(f"上传 {color} 图片失败: {e}")
                
            # 等待上传完成
            await page.wait_for_timeout(4000)
    except Exception as e:
        logger.error(f"上传颜色图片异常: {e}")


async def fill_sizes(page, sizes_text: str):
    """填写尺码值，支持多个尺码（模拟键盘输入）"""
    try:
        # 清理尺码文本，去除特殊符号
        cleaned_text = sizes_text
        if cleaned_text.startswith("['"):
            cleaned_text = cleaned_text[2:]
        if cleaned_text.endswith("']"):
            cleaned_text = cleaned_text[:-2]
        cleaned_text = cleaned_text.replace("'", "").replace("\"", "").replace("[", "").replace("]", "")
        
        # 分割尺码（空格分隔）
        sizes = [s.strip() for s in cleaned_text.split(' ') if s.strip()]
        if not sizes:
            logger.warning("无有效尺码数据")
            return
        
        logger.info(f"准备填写 {len(sizes)} 个尺码: {sizes}")
        
        # 等待尺码输入框出现
        await page.wait_for_timeout(1000)
        
        # 逐个填写尺码
        for i, size in enumerate(sizes):
            logger.info(f"正在填写尺码 {i+1}: {size}")
            
            # 使用 Playwright 的 keyboard.type 方法模拟真实键盘输入
            result = await page.evaluate(_shadow_js_with_arg(f'''
                const goodsSaleParams = shadowRoot.querySelector('.goods-sale-params');
                let inputs = [];
                
                if (goodsSaleParams) {{
                    inputs = goodsSaleParams.querySelectorAll('input[placeholder*="请输入尺码"]');
                }}
                
                if (inputs.length === 0) {{
                    inputs = shadowRoot.querySelectorAll('input[placeholder*="请输入尺码"]');
                }}
                
                if (inputs[{i}]) {{
                    inputs[{i}].click();
                    inputs[{i}].focus();
                    return {{ success: true, index: {i}, inputCount: inputs.length }};
                }}
                return {{ success: false, reason: 'input not found', inputCount: inputs.length }};
            '''), size)
            
            if result.get("success"):
                # 等待输入框获得焦点
                await page.wait_for_timeout(200)
                
                # 使用 keyboard.type 模拟真实键盘输入
                await page.keyboard.type(size, delay=80)
                
                # 按下回车键触发输入完成
                await page.keyboard.press('Enter')
                
                logger.info(f"已填写尺码 {i+1}: {size} (当前输入框数量: {result.get('inputCount', 0)})")
                
                # 如果还有下一个尺码，等待新输入框生成
                if i < len(sizes) - 1:
                    logger.info("等待新的尺码输入框生成...")
                    await page.wait_for_timeout(1200)
            else:
                logger.warning(f"尺码 {i+1} 填写失败: {result.get('reason')} (当前输入框数量: {result.get('inputCount', 0)})")
                await page.wait_for_timeout(1000)
                
    except Exception as e:
        logger.error(f"填写尺码异常: {e}")


async def click_presale_button(page):
    """点击按商品预售按钮"""
    try:
        await page.wait_for_timeout(2000)
        
        result = await page.evaluate(_shadow_js("""
            const goodsSaleParams = shadowRoot.querySelector('.goods-sale-params');
            if (goodsSaleParams) {
                // 方法1：查找包含"按商品预售"或"商品预售"文本的单选按钮
                const labels = goodsSaleParams.querySelectorAll('label, div, span');
                for (const label of labels) {
                    const text = label.textContent || label.innerText || '';
                    if (text.includes('商品预售') || text.includes('按商品预售')) {
                        // 查找关联的 radio 按钮
                        const radio = label.querySelector('input[type="radio"]') || 
                                     label.closest('label')?.querySelector('input[type="radio"]') ||
                                     label.parentElement?.querySelector('input[type="radio"]') ||
                                     label.nextElementSibling?.querySelector('input[type="radio"]');
                        if (radio && !radio.checked) {
                            radio.click();
                            return { success: true, method: 'radio_by_label' };
                        }
                    }
                }
                
                // 方法2：直接查找所有 radio 按钮，通过 value 或 name 判断
                const radios = goodsSaleParams.querySelectorAll('input[type="radio"]');
                for (const radio of radios) {
                    const value = radio.value || '';
                    const name = radio.name || '';
                    const parentText = radio.parentElement?.textContent || '';
                    if (value.includes('presale') || name.includes('presale') || 
                        parentText.includes('预售') || parentText.includes('商品预售')) {
                        if (!radio.checked) {
                            radio.click();
                            return { success: true, method: 'radio_by_value' };
                        }
                    }
                }
            }
            return { success: false, reason: 'presale button not found' };
        """))
        
        if result.get("success"):
            logger.info(f"已点击按商品预售 (方法: {result.get('method')})")
            # 点击后等待预售选项展开
            await page.wait_for_timeout(2000)
        else:
            logger.warning(f"按商品预售点击失败: {result.get('reason')}")
    except Exception as e:
        logger.error(f"按商品预售点击异常: {e}")


async def fill_delivery_days(page, days: str = "15"):
    """填写发货天数"""
    try:
        await page.wait_for_timeout(1500)
        
        result = await page.evaluate(_shadow_js_with_arg("""
            const goodsSaleParams = shadowRoot.querySelector('.goods-sale-params');
            if (goodsSaleParams) {
                // 方法1：查找包含"天"、"发货"、"预售"关键字的输入框
                const inputs = goodsSaleParams.querySelectorAll('input[type="text"], input[type="number"], input:not([type])');
                for (const input of inputs) {
                    const placeholder = input.placeholder || '';
                    const label = input.closest('.weui-desktop-form__item')?.textContent || '';
                    const parentText = input.parentElement?.textContent || '';
                    
                    if (placeholder.includes('天') || placeholder.includes('发货') || 
                        label.includes('天内发货') || label.includes('发货天数') ||
                        parentText.includes('天内发货') || parentText.includes('发货天数')) {
                        input.click();
                        input.focus();
                        return { success: true, method: 'by_keyword' };
                    }
                }
                
                // 方法2：查找预售相关区域的第一个数字输入框
                const presaleArea = Array.from(goodsSaleParams.querySelectorAll('div')).find(div => 
                    (div.textContent || '').includes('预售') || (div.textContent || '').includes('发货')
                );
                if (presaleArea) {
                    const input = presaleArea.querySelector('input[type="number"], input[type="text"]');
                    if (input) {
                        input.click();
                        input.focus();
                        return { success: true, method: 'by_presale_area' };
                    }
                }
            }
            return { success: false, reason: 'delivery days input not found' };
        """), days)
        
        if result.get("success"):
            await page.wait_for_timeout(200)
            await page.keyboard.type(days, delay=80)
            logger.info(f"已填写发货天数: {days} (方法: {result.get('method')})")
        else:
            logger.warning(f"发货天数填写失败: {result.get('reason')}")
    except Exception as e:
        logger.error(f"发货天数填写异常: {e}")


async def fill_price_and_stock(page, price: str, stock: str = "10"):
    """填写售卖价和库存"""
    try:
        await page.wait_for_timeout(1000)
        
        # 填写售卖价
        result = await page.evaluate(_shadow_js_with_arg("""
            const goodsSaleParams = shadowRoot.querySelector('.goods-sale-params');
            if (goodsSaleParams) {
                // 查找售卖价输入框
                const inputs = goodsSaleParams.querySelectorAll('input[type="text"], input[type="number"]');
                for (const input of inputs) {
                    const placeholder = input.placeholder || '';
                    const label = input.closest('.weui-desktop-form__item')?.querySelector('label')?.textContent || '';
                    if (placeholder.includes('售卖价') || label.includes('售卖价') || placeholder.includes('价格')) {
                        input.click();
                        input.focus();
                        return { success: true, field: 'price' };
                    }
                }
            }
            return { success: false, reason: 'price input not found' };
        """), price)
        
        if result.get("success"):
            await page.wait_for_timeout(200)
            await page.keyboard.type(price, delay=80)
            await page.keyboard.press('Tab')
            logger.info(f"已填写售卖价: {price}")
        else:
            logger.warning(f"售卖价填写失败: {result.get('reason')}")
        
        await page.wait_for_timeout(500)
        
        # 填写库存
        result = await page.evaluate(_shadow_js_with_arg("""
            const goodsSaleParams = shadowRoot.querySelector('.goods-sale-params');
            if (goodsSaleParams) {
                // 查找库存输入框
                const inputs = goodsSaleParams.querySelectorAll('input[type="text"], input[type="number"]');
                for (const input of inputs) {
                    const placeholder = input.placeholder || '';
                    const label = input.closest('.weui-desktop-form__item')?.querySelector('label')?.textContent || '';
                    if (placeholder.includes('库存') || label.includes('库存')) {
                        input.click();
                        input.focus();
                        return { success: true, field: 'stock' };
                    }
                }
            }
            return { success: false, reason: 'stock input not found' };
        """), stock)
        
        if result.get("success"):
            await page.wait_for_timeout(200)
            await page.keyboard.type(stock, delay=80)
            logger.info(f"已填写库存: {stock}")
        else:
            logger.warning(f"库存填写失败: {result.get('reason')}")
    except Exception as e:
        logger.error(f"价格库存填写异常: {e}")


async def click_setting_button(page):
    """点击设置按钮"""
    try:
        await page.wait_for_timeout(2000)
        
        result = await page.evaluate(_shadow_js("""
            const goodsSaleParams = shadowRoot.querySelector('.goods-sale-params');
            if (goodsSaleParams) {
                // 查找设置按钮
                const buttons = goodsSaleParams.querySelectorAll('button, .weui-desktop-btn');
                for (const btn of buttons) {
                    const text = btn.textContent || btn.innerText || '';
                    if (text.includes('设置') && !text.includes('取消')) {
                        btn.click();
                        return { success: true };
                    }
                }
            }
            return { success: false, reason: 'setting button not found' };
        """))
        
        if result.get("success"):
            logger.info("已点击设置按钮")
        else:
            logger.warning(f"设置按钮点击失败: {result.get('reason')}")
    except Exception as e:
        logger.error(f"设置按钮点击异常: {e}")


async def process_single_item(page, item: dict, index: int):
    """处理单个商品上架"""
    logger.info(f"\n--- 正在处理第 {index} 条 ---")
    image_path = item.get("image_path")
    title = item.get("title")
    material = item.get("material")
    color = item.get("color")
    style = item.get("style")
    color_image_paths = item.get("color_image_paths", "")
    price = item.get("price")
    safety_level = item.get("safety_level")

    logger.info(f"标题: {title} | 图片: {image_path}")
    logger.info(f"面料: {material} | 颜色: {color} | 风格: {style}")
    logger.info(f"颜色图片路径: {color_image_paths}")
    logger.info(f"售卖价: {price} | 安全等级: {safety_level}")

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

        # 5. 填写面料材质成分含量（固定100%）
        await fill_material_percentage(page, "100")

        # 6. 填写颜色
        if color:
            await fill_input_field(page, "颜色", str(color), "颜色")

        # 7. 选择风格（无结果时选择"其他"）
        if style:
            await select_style(page, str(style))

        # 8. 选择安全等级（为空时选择"其他"）
        await select_safety_level(page, str(safety_level) if safety_level else "")

        # 9. 选择使用年龄（选择"全选"）
        await select_age_range(page)

        # 10. 点击创建新规格
        await click_create_spec(page)
        await page.wait_for_timeout(1000)

        # 11. 选择颜色选项
        await select_size_color(page)
        await page.wait_for_timeout(1000)
        
        # 12. 填写颜色值
        if color:
            await fill_colors(page, str(color))
            await page.wait_for_timeout(2000)
            
            # 13. 上传颜色对应图片
            if color_image_paths:
                await upload_color_images(page, color_image_paths, color)
                await page.wait_for_timeout(2000)
                
                # 14. 再次点击创建新规格
                await click_create_spec(page)
                await page.wait_for_timeout(1000)
                
                # 15. 填写尺码
                sizes = item.get("sizes")
                if sizes:
                    await fill_sizes(page, str(sizes))
                    await page.wait_for_timeout(2000)
        
        # 16. 点击按商品预售
        await click_presale_button(page)
        await page.wait_for_timeout(1000)
        
        # 17. 填写发货天数
        await fill_delivery_days(page, "15")
        await page.wait_for_timeout(1000)
        
        # 18. 填写售卖价和库存
        if price:
            await fill_price_and_stock(page, str(price), "10")
            await page.wait_for_timeout(1000)
        
        # 19. 点击设置按钮
        await click_setting_button(page)

    await page.wait_for_timeout(3000)
    logger.info(f"第 {index} 条处理完成")


async def run_uploader():
    """批量上架商品到微信小商店"""
    if not os.path.exists(WEIXIN_STATE_FILE):
        logger.error(f"未找到 {WEIXIN_STATE_FILE}，请先运行 login/weixin_login.py")
        return

    data = read_upload_data(UPLOAD_EXCEL, UPLOAD_COLUMNS)
    if not data:
        logger.error("无可用上架数据")
        return

    logger.info(f"共 {len(data)} 条商品待上架")

    async with async_playwright() as p:
        browser = await launch_browser(p, channel=BROWSER_CHANNEL)
        context = await create_context(
            browser, state_file=WEIXIN_STATE_FILE, no_viewport=True
        )
        page = await context.new_page()

        for i, item in enumerate(data, 1):
            # 每条商品都导航到发布页
            await page.goto(WEIXIN_GOODS_URL)
            logger.info("等待页面及微应用加载...")
            await asyncio.sleep(5)
            await handle_popups(page)

            try:
                await page.wait_for_selector(WEIXIN_MICRO_APP, timeout=20000)
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