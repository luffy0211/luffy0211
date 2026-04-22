from playwright.sync_api import sync_playwright
import json
import os
import time
import requests
import random
import openpyxl
from pathlib import Path

from config import E3E3_STATE_FILE, STATE_DIR, DESKTOP_PATH, IMAGE_ROOT

# 登录状态文件路径
LOGIN_STATE_FILE = E3E3_STATE_FILE

def write_to_excel(data, product_data=None, image_paths=None, filename='3e3e_products.xlsx'):
    """将数据写入Excel文件（覆盖写入，只保留最新数据）"""
    desktop_path = str(Path.home() / "Desktop")
    filename = os.path.join(desktop_path, filename)
    
    # 如果文件存在，删除旧文件
    if os.path.exists(filename):
        try:
            os.remove(filename)
        except:
            pass
    
    # 创建新文件
    wb = openpyxl.Workbook()
    ws = wb.active
    headers = ['商品链接', '商品名称', '价格', '店铺名称', '', '风格', '颜色分类', '适用季节', '材质成分', '面料', '安全等级', '', '', '主图', '', '', '', 'SKU图片', '身高']
    ws.append(headers)
    
    # 从product_data中提取属性
    attrs = product_data.get('attributes', []) if product_data else []
    colors = product_data.get('colors', []) if product_data else []
    sizes = product_data.get('sizes', []) if product_data else []
    
    style = ''
    fabric = ''
    season = ''
    material = ''
    safety = ''
    height = ''
    
    # 从attributes中匹配所有字段
    for attr in attrs:
        # 风格
        if '风格：' in attr:
            style = attr.replace('风格：', '').replace('风格：', '').strip()
        # 面料
        elif '面料：' in attr:
            fabric = attr.replace('面料：', '').replace('面料：', '').strip()
        # 适用季节
        elif '适用季节：' in attr:
            season = attr.replace('适用季节：', '').replace('适用季节：', '').strip()
        # 材质成分
        elif '材质成分：' in attr:
            material = attr.replace('材质成分：', '').replace('材质成分：', '').strip()
        # 安全类别/安全等级
        elif '安全类别：' in attr or '安全等级：' in attr:
            safety = attr.replace('安全类别：', '').replace('安全等级：', '').strip()
        # 身高
        elif '身高：' in attr:
            height = attr.replace('身高：', '').replace('身高：', '').strip()
    
    # 颜色用空格分隔
    color_str = ' '.join(colors) if colors else ''
    
    # 主图和SKU图路径只保留文件夹路径（从第一个文件路径提取）
    main_path = image_paths.get('main', '') if image_paths else ''
    sku_path = image_paths.get('sku', '') if image_paths else ''
    
    # 从第一个文件路径提取文件夹
    main_folder = os.path.dirname(main_path.split(';')[0].strip()) if main_path else ''
    sku_folder = os.path.dirname(sku_path.split(';')[0].strip()) if sku_path else ''
    
    # 商品名称去掉"复制"和空格
    title = data.get('title', '').replace('复制', '').replace(' ', '').strip()
    
    row_data = [
        data.get('product_url', ''),
        title,
        data.get('price', ''),
        data.get('shop_name', ''),
        '',
        style,
        color_str,
        season,
        material,
        fabric,
        safety,
        '',
        '',
        main_folder,
        '',
        '',
        '',
        sku_folder,
        height,
    ]
    ws.append(row_data)
    wb.save(filename)
    print(f"数据已保存到: {filename}")

def download_images(product_name, image_urls):
    """下载图片到桌面童装文件夹"""
    image_paths = {'main': '', 'sku': ''}
    
    safe_name = "".join(c for c in product_name if c not in r'\/:*?"<>|').strip()[:50]
    if not safe_name:
        safe_name = "product"
    
    product_folder = os.path.join(IMAGE_ROOT, safe_name)
    main_folder = product_folder
    sku_folder = os.path.join(product_folder, 'sku')
    
    os.makedirs(main_folder, exist_ok=True)
    os.makedirs(sku_folder, exist_ok=True)
    
    print(f"图片保存目录: {product_folder}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://www.3e3e.cn/',
    }
    
    main_paths = []
    sku_paths = []
    
    # 区分主图和SKU图
    # https开头是主图，http开头是SKU图
    main_images = [url for url in image_urls if url.startswith('https')]
    sku_images = [url for url in image_urls if url.startswith('http') and not url.startswith('https')]
    
    # 下载主图
    print(f"正在下载主图...")
    for i, src in enumerate(main_images):
        try:
            print(f"  正在下载主图 {i+1}/{len(main_images)}...")
            response = requests.get(src, timeout=15, headers=headers)
            
            if response.status_code == 200:
                ext = '.jpg'
                if '.png' in src:
                    ext = '.png'
                
                filename = f"主图_{i+1}{ext}"
                filepath = os.path.join(main_folder, filename)
                main_paths.append(filepath)
                
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                
                print(f"    已保存: {filename}")
            else:
                print(f"    下载失败，状态码: {response.status_code}")
            
            time.sleep(random.uniform(0.3, 0.8))
            
        except Exception as e:
            print(f"    下载失败: {e}")
            continue
    
    # 下载SKU图
    print(f"正在下载SKU图...")
    for i, src in enumerate(sku_images):
        try:
            print(f"  正在下载SKU图 {i+1}/{len(sku_images)}...")
            response = requests.get(src, timeout=15, headers=headers)
            
            if response.status_code == 200:
                ext = '.jpg'
                if '.png' in src:
                    ext = '.png'
                
                filename = f"SKU_{i+1}{ext}"
                filepath = os.path.join(sku_folder, filename)
                sku_paths.append(filepath)
                
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                
                print(f"    已保存: {filename}")
            else:
                print(f"    下载失败，状态码: {response.status_code}")
            
            time.sleep(random.uniform(0.3, 0.8))
            
        except Exception as e:
            print(f"    下载失败: {e}")
            continue
    
    image_paths['main'] = '; '.join(main_paths)
    image_paths['sku'] = '; '.join(sku_paths)
    
    print(f"图片下载完成！主图: {len(main_paths)}张, SKU图: {len(sku_paths)}张")
    
    return image_paths

def login_and_save_state():
    """登录并保存登录状态"""
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,  # 非无头模式，方便手动登录
            channel="msedge"
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = context.new_page()
        
        # 访问登录页面
        page.goto("https://www.3e3e.cn/login", timeout=60000)
        print("请在浏览器中完成登录操作...")
        
        # 等待用户手动登录完成
        input("登录完成后请按回车键继续...")
        
        # 保存登录状态
        context.storage_state(path=LOGIN_STATE_FILE)
        print(f"登录状态已保存到 {LOGIN_STATE_FILE}")
        
        browser.close()

def crawl_3e3e_product(url):
    with sync_playwright() as p:
        # 检查是否有登录状态文件
        storage_state = LOGIN_STATE_FILE if os.path.exists(LOGIN_STATE_FILE) else None
        
        # 启动 Edge 浏览器
        browser = p.chromium.launch(
            headless=False,
            channel="msedge"
        )
        
        # 创建上下文时加载登录状态
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            storage_state=storage_state
        )
        page = context.new_page()

        try:
            # 访问商品页
            page.goto(url, timeout=60000)
            page.wait_for_load_state("networkidle")

            # 等待商品标题出现
            print("等待页面加载...")
            try:
                page.wait_for_selector(".product-details h5", timeout=30000)
            except Exception:
                print("标题选择器超时，等待页面继续加载...")
                page.wait_for_timeout(5000)
                if not page.locator(".product-details h5").count():
                    raise TimeoutError("等待商品标题超时，页面可能未正确加载或需要登录")

            # 开始抓取数据
            data = {}

            # 1. 商品标题
            data["title"] = page.locator(".product-details h5").inner_text().strip()
            
            # 商品名称去掉"复制"并去除所有空格
            title = data.get('title', '').replace('复制', '').replace(' ', '').strip()
            data["title"] = title

            # 3. 价格
            try:
                data["price"] = page.locator(".product-price-info strong i").inner_text().strip()
            except Exception:
                data["price"] = ""

            images = []
            
            # 抓取主图和缩略图
            imgs = page.locator(".small-img-list img")
            count = imgs.count()
            for i in range(count):
                src = imgs.nth(i).get_attribute("data-url")
                if src and src not in images:
                    images.append(src)
            
            # 抓取 sku-wrap 中的图片
            sku_imgs = page.locator("ul.sku-wrap img")
            sku_count = sku_imgs.count()
            for i in range(sku_count):
                src = sku_imgs.nth(i).get_attribute("src") or sku_imgs.nth(i).get_attribute("data-url")
                if src and src not in images:
                    images.append(src)
            
            data["images"] = images

            # 7. 商品视频
            try:
                data["video_url"] = page.locator("#video-flv").get_attribute("src")
            except Exception:
                data["video_url"] = ""

            # 8. 颜色
            colors = []
            color_items = page.locator(".sku-warp-li")
            for i in range(color_items.count()):
                color = color_items.nth(i).get_attribute("data-color")
                if color:
                    colors.append(color)
            data["colors"] = colors

            # 9. 尺码
            sizes = []
            size_items = page.locator(".sku-size")
            for i in range(size_items.count()):
                size = size_items.nth(i).inner_text().strip()
                if size:
                    sizes.append(size)
            data["sizes"] = sizes

            # 10. 店铺信息
            try:
                data["shop_name"] = page.locator(".supplier-name a").inner_text().strip()
            except Exception:
                data["shop_name"] = ""
            try:
                data["shop_url"] = page.locator(".supplier-name a").get_attribute("href")
            except Exception:
                data["shop_url"] = ""
            try:
                data["shop_address"] = page.locator(".desc").inner_text().strip()
            except Exception:
                data["shop_address"] = ""

            # 12. 商品属性（风格、季节、材质、功能等）
            attrs = []
            attr_items = page.locator(".details-attribute-item")
            for i in range(attr_items.count()):
                attrs.append(attr_items.nth(i).inner_text().strip())
            data["attributes"] = attrs

            # 13. 商品ID（从页面提取）
            try:
                data["product_id"] = page.locator(".product-collect-btn").get_attribute("monitor-productid")
            except Exception:
                data["product_id"] = ""

            return data
        finally:
            browser.close()


if __name__ == "__main__":
    # 检查是否需要登录
    if not os.path.exists(LOGIN_STATE_FILE):
        print("未找到登录状态文件，开始登录...")
        login_and_save_state()
    else:
        print("使用已保存的登录状态...")
    
    # 这里替换成你要抓的商品链接
    target_url = "https://www.3e3e.cn/product/cemqaia.html?from=search&amp;dataFrom=ad3&amp;requestKey=QTdcd6LZN6SE9f7T83PoajfXaflbmRrP:1775671666237&amp;costPosition=search/list&amp;adRmdTrace=&amp;advertOrderId=&amp;advertCode="
    
    result = crawl_3e3e_product(target_url)
    
    # 打印抓取结果
    print("\n" + "="*50)
    print(f"【商品名称】: {result.get('title', '')}")
    print(f"【价格】: {result.get('price', '')}")
    print(f"【店铺名称】: {result.get('shop_name', '')}")
    print(f"【图片数量】: {len(result.get('images', []))}")
    print(f"【颜色数量】: {len(result.get('colors', []))}")
    print(f"【尺码数量】: {len(result.get('sizes', []))}")
    print(f"【属性数量】: {len(result.get('attributes', []))}")
    
    if result.get('attributes'):
        print("\n【商品属性】:")
        for attr in result.get('attributes', []):
            print(f"  {attr}")
    
    # 下载图片
    print("\n正在下载商品图片...")
    image_paths = download_images(result.get('title', 'product'), result.get('images', []))
    
    # 写入Excel
    write_to_excel({
        'title': result.get('title', ''),
        'price': result.get('price', ''),
        'product_url': target_url,
        'shop_name': result.get('shop_name', ''),
    }, result, image_paths)
    
    # 保存为 JSON 文件
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    product_id = result.get('product_id', 'unknown')
    filename = f"3e3e_product_{product_id}_{timestamp}.json"
    
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"\nJSON数据已保存到: {filename}")
    print("="*50)