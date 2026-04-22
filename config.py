import os
from pathlib import Path

# ==================== 路径配置 ====================
DESKTOP_PATH = str(Path.home() / "Desktop")
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_DIR = os.path.join(PROJECT_DIR, "state")

# 状态文件
TAOBAO_STATE_FILE = os.path.join(STATE_DIR, "taobao_state.json")
WEIXIN_STATE_FILE = os.path.join(STATE_DIR, "weixin_state.json")
SHIPINHAO_STATE_FILE = os.path.join(STATE_DIR, "shipinhao_state.json")
XHS_STATE_FILE = os.path.join(STATE_DIR, "xiaohongshu_state.json")
E3E3_STATE_FILE = os.path.join(STATE_DIR, "3e3e_state.json")

# Excel 文件（桌面）
UPLOAD_EXCEL = os.path.join(DESKTOP_PATH, "影刀上架参数.xlsx")
SHIPINHAO_UPLOAD_EXCEL = os.path.join(DESKTOP_PATH, "影刀上架参数.xlsx")
URLS_EXCEL = os.path.join(DESKTOP_PATH, "urls.xlsx")
OUTPUT_EXCEL = os.path.join(DESKTOP_PATH, "taobao_products.xlsx")

# 图片根目录
IMAGE_ROOT = os.path.join(DESKTOP_PATH, "童装")

# ==================== 浏览器配置 ====================
BROWSER_CHANNEL = "msedge"
BROWSER_ARGS = [
    "--start-maximized",
    "--disable-blink-features=AutomationControlled",
    "--disable-dev-shm-usage",
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-infobars",
    "--window-size=1920,1080",
]
VIEWPORT = {"width": 1920, "height": 1080}

# ==================== 天猫选择器 ====================
TMALL_SELECTORS = {
    "title": "span.mainTitle--R75fTcZL",
    "price_platform": "div.highlightPrice--LlVWiXXs span.text--LP7Wf49z",
    "price_shop": "div.highlightPrice--asfw5V1e span.text--jyiUrkMu",
    "price_fallback": "span.text--jyiUrkMu",
    "param_general": "div.generalParamsInfoItem--qLqLDVWp",
    "param_general_title": ".generalParamsInfoItemTitle--Fo9kKj5Z",
    "param_general_value": ".generalParamsInfoItemSubTitle--S4pgp6b9",
    "param_emphasis": "div.emphasisParamsInfoItem--H5Qt3iog",
    "param_emphasis_title": ".emphasisParamsInfoItemSubTitle--Lzwb8yjJ",
    "param_emphasis_value": ".emphasisParamsInfoItemTitle--IGClES8z",
    "main_image": 'xpath=//img[contains(@class, "thumbnailPic--QasTmWDm")]',
    "sku_image": 'xpath=//img[contains(@class, "valueItemImg--GC9bH5my")]',
}

# 需要采集的参数字段
PARAM_FIELDS = ["风格", "面料", "适用性别", "颜色分类", "身高", "适用季节", "材质成分", "安全等级"]

# Excel 输出表头
OUTPUT_HEADERS = [
    "商品名称", "平台加补后价格", "风格", "面料", "适用性别",
    "颜色分类", "身高", "适用季节", "材质成分", "安全等级",
    "主图", "SKU图片", "商品链接", "抓取时间",
]

# 上架 Excel 列映射（1-based）
UPLOAD_COLUMNS = {
    "style": 6,       # F列：风格
    "color": 7,       # G列：颜色（多个颜色空格分隔）
    "material": 9,    # I列：面料材质
    "safety_level": 11, # K列：安全等级
    "image_path": 14, # N列：主图路径
    "title": 15,      # O列：标题
    "price": 16,      # P列：售卖价
    "sizes": 19,      # S列：尺码（多个尺码空格分隔）
    "color_image_paths": 18, # R列：颜色图片路径（多个路径空格分隔）
}

# ==================== 微信上架选择器 ====================
WEIXIN_GOODS_URL = "https://store.weixin.qq.com/shop/goods/entry"
WEIXIN_MICRO_APP = 'micro-app[name="goods"]'

# ==================== 视频号上架配置 ====================
SHIPINHAO_GOODS_URL = "https://store.weixin.qq.com/shop/goods/entry"
SHIPINHAO_MICRO_APP = 'micro-app[name="goods"]'

# ==================== 小红书上架配置 ====================
XHS_GOODS_URL = "https://ark.xiaohongshu.com/app-item/good/create"
XHS_UPLOAD_EXCEL = os.path.join(DESKTOP_PATH, "影刀上架参数.xlsx")

# 小红书 Excel 列映射
XHS_UPLOAD_COLUMNS = {
    "price": 3,              # C列：价格（用于计算市场价 = 价格*3）
    "style": 6,              # F列：风格
    "color": 7,              # G列：颜色分类（空格分隔）
    "season": 8,             # H列：适应季节
    "material_composition": 9, # I列：材质成分（空格分隔，可多个）
    "fabric": 10,            # J列：面料
    "safety_level": 11,      # K列：安全等级
    "image_path": 14,        # N列：主图路径
    "title": 15,             # O列：商品标题
    "sale_price": 16,        # P列：售价
    "color_image_paths": 18, # R列：颜色图片路径（空格分隔）
    "sizes": 19,             # S列：尺码（空格分隔，只取数字）
}

# ==================== 抖店上架配置 ====================
DOUDIAN_STATE_FILE = os.path.join(STATE_DIR, "doudian_state.json")
DOUDIAN_GOODS_URL = "https://fxg.jinritemai.com/ffa/g/create"
DOUDIAN_LOGIN_URL = "https://fxg.jinritemai.com/index.html"
DOUDIAN_UPLOAD_EXCEL = os.path.join(DESKTOP_PATH, "影刀上架参数.xlsx")

# 抖店 Excel 列映射（与小红书相同）
DOUDIAN_UPLOAD_COLUMNS = {
    "price": 3,              # C列：价格（用于计算市场价 = 价格*3）
    "style": 6,              # F列：风格
    "color": 7,              # G列：颜色分类（空格分隔）
    "season": 8,             # H列：适应季节
    "material_composition": 9, # I列：材质成分（空格分隔，可多个）
    "fabric": 10,            # J列：面料
    "safety_level": 11,      # K列：安全等级
    "image_path": 14,        # N列：主图路径
    "title": 15,             # O列：商品标题
    "sale_price": 16,        # P列：售价
    "color_image_paths": 18, # R列：颜色图片路径（空格分隔）
    "sizes": 19,             # S列：尺码（空格分隔，只取数字）
}

# ==================== 下载配置 ====================
DOWNLOAD_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://detail.tmall.com/",
    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}
MAX_CONCURRENT_DOWNLOADS = 3
DOWNLOAD_TIMEOUT = 15
MAX_RETRIES = 3
RETRY_DELAY = 3

# ==================== 图片扩展名 ====================
IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"]