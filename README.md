# 电商自动化工具集

基于 Playwright 的电商自动化工具，实现从淘宝/天猫/3e3e 采集童装商品数据，并自动批量上架到微信小商店、视频号小店、小红书、抖店。

## 功能特性

- **商品采集** — 批量抓取天猫/淘宝/3e3e 商品标题、价格、参数、主图、SKU 图
- **多平台上架** — 微信小商店、视频号小店、小红书、抖店一键批量上架
- **登录管理** — 扫码登录，状态持久化，支持多平台
- **反检测** — playwright-stealth 指纹伪装 + 随机延迟
- **异步下载** — aiohttp 并发下载图片，指数退避重试

## 技术栈

- **Python** + **Playwright**（异步 API）
- **openpyxl** — Excel 读写
- **aiohttp** — 异步图片下载
- **playwright-stealth** — 浏览器指纹伪装
- **浏览器** — Microsoft Edge (Chromium)

## 项目结构

```
├── main.py                    # 统一入口（命令行参数）
├── config.py                  # 全局配置（路径、选择器、常量）
├── 3e3e.py                    # 3e3e 平台抓取脚本
├── taobao asyncio.py          # 淘宝异步抓取脚本
├── utils/                     # 工具库
│   ├── browser.py             #   浏览器启动 / 反检测 / 弹窗处理
│   ├── excel.py               #   Excel 读写
│   ├── image.py               #   图片下载 / URL 修复
│   └── logger.py              #   日志系统
├── login/                     # 登录模块
│   ├── taobao_login.py        #   淘宝扫码登录
│   ├── weixin_login.py        #   微信登录
│   ├── shipinhao_login.py     #   视频号登录
│   ├── xiaohongshu_login.py   #   小红书登录
│   └── doudian_login.py       #   抖店登录
├── crawler/                   # 采集模块
│   └── tmall_crawler.py       #   天猫商品批量采集
├── uploader/                  # 上架模块
│   ├── weixin_uploader.py     #   微信小商店
│   ├── shipinhao_uploader.py  #   视频号小店
│   ├── xiaohongshu_uploader.py#   小红书
│   └── doudian_uploader.py    #   抖店
├── state/                     # 登录状态（不提交 Git）
├── logs/                      # 运行日志
├── data/                      # 数据文件
└── docs/                      # 使用文档
```

## 安装

```bash
pip install playwright openpyxl aiohttp playwright-stealth
playwright install chromium
```

## 使用方法

```bash
# 1. 登录（首次或状态过期时执行）
python main.py login taobao        # 淘宝扫码登录
python main.py login weixin        # 微信登录
python main.py login shipinhao     # 视频号登录
python main.py login doudian       # 抖店登录

# 2. 采集商品（从桌面 urls.xlsx 读取 URL）
python main.py crawl

# 3. 上架商品（从桌面 影刀上架参数.xlsx 读取）
python main.py upload              # 微信小商店
python main.py upload-channels     # 视频号小店
python main.py upload-doudian      # 抖店
```

## 工作流程

```
登录保存状态 → 批量采集商品数据 → 保存到 Excel → 批量上架到各平台
```

## 数据规范

### 输入
- **urls.xlsx**（桌面）— A 列存放商品 URL，每行一个
- **影刀上架参数.xlsx**（桌面）— 上架参数（风格、颜色、面料、图片路径、标题、售价、尺码等）

### 输出
- **taobao_products.xlsx**（桌面）— 采集结果
- **桌面/童装/{商品标题}/** — 主图 + SKU 图片

## 注意事项

- `state/` 目录包含登录凭证，已加入 `.gitignore`
- 采集频率通过随机延迟控制，避免触发平台风控
- 首次使用需扫码登录各平台
