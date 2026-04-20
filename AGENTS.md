<coding_guidelines>
# 项目概述

基于 Playwright 的电商自动化工具集，实现从淘宝/天猫/3e3e 采集童装商品数据，并自动批量上架到微信小商店、视频号小店、小红书、抖店。

## 技术栈

- **Python** + **Playwright**（异步 API）
- **openpyxl** — Excel 读写
- **aiohttp** — 异步图片下载（并发控制 + 指数退避重试）
- **playwright-stealth** — 浏览器指纹伪装
- **logging** — 统一日志（控制台 + 文件）
- **浏览器** — Microsoft Edge (Chromium)

## 项目结构

```
D:\zsh\
├── main.py                        # 统一入口（命令行参数）
├── config.py                      # 全局配置（路径、选择器、常量）
├── 3e3e.py                        # 3e3e 平台抓取脚本
├── taobao asyncio.py              # 淘宝异步抓取脚本
├── AGENTS.md                      # 项目说明
├── .gitignore
├── utils/
│   ├── __init__.py
│   ├── logger.py                  # 日志系统
│   ├── excel.py                   # Excel 读写（统一实现）
│   ├── browser.py                 # 浏览器启动/反检测/弹窗处理
│   └── image.py                   # 图片下载/路径处理
├── login/
│   ├── __init__.py
│   ├── taobao_login.py            # 淘宝扫码登录
│   ├── weixin_login.py            # 微信登录
│   ├── shipinhao_login.py         # 视频号登录
│   ├── xiaohongshu_login.py       # 小红书登录
│   └── doudian_login.py           # 抖店登录
├── crawler/
│   ├── __init__.py
│   └── tmall_crawler.py           # 天猫商品批量采集
├── uploader/
│   ├── __init__.py
│   ├── weixin_uploader.py         # 微信小商店批量上架
│   ├── shipinhao_uploader.py      # 视频号小店批量上架
│   ├── xiaohongshu_uploader.py    # 小红书批量上架
│   └── doudian_uploader.py        # 抖店批量上架
├── state/                         # 登录状态文件（不提交 Git）
│   ├── taobao_state.json
│   ├── weixin_state.json
│   ├── shipinhao_state.json
│   ├── xiaohongshu_state.json
│   └── doudian_state.json
├── logs/                          # 运行日志
├── data/                          # 数据文件 / 图片
├── docs/                          # 使用文档 / 说明
│   └── 计划书.md
└── archive/                       # 旧版文件归档（不提交 Git）
```

## 使用方法

```bash
# 1. 登录（首次或状态过期时执行）
python main.py login taobao        # 淘宝扫码登录
python main.py login weixin        # 微信登录
python main.py login shipinhao     # 视频号登录
python main.py login doudian       # 抖店登录

# 2. 采集商品（从桌面 urls.xlsx 读取URL，支持批量）
python main.py crawl

# 3. 上架商品
python main.py upload              # 微信小商店
python main.py upload-channels     # 视频号小店
python main.py upload-doudian      # 抖店
```

## 工作流程

```
登录保存状态 → 批量采集商品(标题/价格/参数/图片) → 保存到 Excel → 批量上架到各平台
```

## 模块说明

### config.py
集中管理所有配置：文件路径、浏览器参数、CSS 选择器（天猫页面哈希类名）、下载参数、各平台 Excel 列映射等。选择器更新时只需修改此文件。

### 3e3e.py / taobao asyncio.py
独立抓取脚本，分别用于 3e3e 平台和淘宝平台的商品数据采集。

### utils/browser.py
- `launch_browser()` — 统一浏览器启动配置
- `create_context()` — 创建上下文（支持状态恢复、stealth）
- `apply_stealth()` — 反检测（优先用 playwright-stealth，降级为内置脚本）
- `handle_popups()` — 弹窗清理（主文档 + Shadow DOM）
- `check_login_state()` — 登录态验证

### utils/image.py
- `download_image()` — 单张异步下载（指数退避重试）
- `download_images_batch()` — 批量并发下载（Semaphore 限制并发数）
- `fix_image_url()` — URL 修复（协议补全、缩略图还原）

### utils/excel.py
- `read_urls()` — 读取采集 URL 列表（支持多行）
- `read_upload_data()` — 读取上架参数（列映射可配置）
- `write_product_data()` — 采集结果写入

### crawler/tmall_crawler.py
批量采集天猫商品：遍历 urls.xlsx 中所有 URL，提取标题、价格、8 项参数、主图和 SKU 图，写入 Excel。商品间随机延迟 3-6 秒。

### uploader/
- **weixin_uploader.py** — 微信小商店批量上架
- **shipinhao_uploader.py** — 视频号小店批量上架
- **xiaohongshu_uploader.py** — 小红书批量上架
- **doudian_uploader.py** — 抖店批量上架

## 数据规范

### 输入：urls.xlsx（桌面）
A 列存放天猫商品 URL，每行一个。

### 输入：影刀上架参数.xlsx（桌面）
F 列=风格, G 列=颜色, H 列=季节, I 列=面料材质, K 列=安全等级, N 列=图片路径, O 列=标题, P 列=售价, R 列=颜色图片路径, S 列=尺码

### 输出：taobao_products.xlsx（桌面）
商品名称, 价格, 风格, 面料, 适用性别, 颜色分类, 身高, 适用季节, 材质成分, 安全等级, 主图路径, SKU 图片路径, 商品链接, 抓取时间

### 图片输出结构
```
桌面/童装/{商品标题}/
├── {商品标题}_主图_1.jpg
├── ...
└── cq/
    ├── {商品标题}_SKU_1.jpg
    └── ...
```

## 安全注意事项

- `state/` 目录下的 JSON 文件包含登录凭证，已加入 `.gitignore`
- `archive/` 目录包含旧版文件，已加入 `.gitignore`
- 采集频率通过随机延迟控制，避免触发平台风控
- 敏感信息不输出到日志
</coding_guidelines>
