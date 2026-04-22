# 电商自动化管理系统

基于 **Playwright + FastAPI + React** 的电商自动化工具集，实现从淘宝/天猫/3e3e 采集童装商品数据，并自动批量上架到微信小商店、视频号小店、小红书、抖店。

## ✨ 功能概览

| 模块 | 说明 |
|------|------|
| 🔐 登录管理 | 淘宝、微信、视频号、小红书、抖店、千牛、3e3e 扫码登录，状态持久化 |
| 🕷️ 商品采集 | 批量采集天猫/淘宝/3e3e 商品（标题、价格、参数、主图、SKU图） |
| 📤 批量上架 | 一键分发到微信小商店、视频号小店、小红书、抖店 |
| 📊 Web 管理后台 | 仪表盘、商品管理、任务调度、平台状态监控 |
| ⏰ 任务调度 | 立即执行 / 定时执行 / Cron 表达式 |

## 🛠️ 技术栈

**后端**
- Python 3.11+
- FastAPI + Uvicorn（异步 Web 服务）
- SQLAlchemy 2.0 + aiosqlite（异步 ORM）
- Playwright（浏览器自动化）
- playwright-stealth（反检测）
- aiohttp（异步图片下载）
- APScheduler（任务调度）

**前端**
- React 19 + TypeScript
- Vite（构建工具）
- TailwindCSS 4（样式）
- Axios（HTTP 客户端）
- Lucide React（图标）
- React Router 7（路由）

## 📂 项目结构

```
├── main.py                    # CLI 统一入口
├── config.py                  # 全局配置（路径、选择器、常量）
├── start.py                   # Web 后端启动脚本
├── 3e3e.py                    # 3e3e 平台独立抓取脚本
├── taobao asyncio.py          # 淘宝独立抓取脚本
├── utils/
│   ├── logger.py              # 日志系统
│   ├── excel.py               # Excel 读写
│   ├── browser.py             # 浏览器启动 / 反检测 / 弹窗处理
│   └── image.py               # 图片下载 / 路径处理
├── login/
│   ├── taobao_login.py        # 淘宝扫码登录
│   ├── weixin_login.py        # 微信登录
│   ├── shipinhao_login.py     # 视频号登录
│   ├── xiaohongshu_login.py   # 小红书登录
│   ├── doudian_login.py       # 抖店登录
│   ├── qianniu_login.py       # 千牛登录
│   └── e3e3_login.py          # 3e3e 登录
├── crawler/
│   └── tmall_crawler.py       # 天猫商品批量采集
├── uploader/
│   ├── weixin_uploader.py     # 微信小商店批量上架
│   ├── shipinhao_uploader.py  # 视频号小店批量上架
│   ├── xiaohongshu_uploader.py# 小红书批量上架
│   └── doudian_uploader.py    # 抖店批量上架
├── server/                    # FastAPI 后端服务
│   ├── app.py                 # 应用入口
│   ├── database.py            # 数据库配置
│   ├── models.py              # ORM 模型
│   ├── routers/               # API 路由
│   └── services/              # 业务服务层
├── web/                       # React 前端
│   ├── src/
│   │   ├── App.tsx            # 主布局 + 路由
│   │   ├── api/client.ts      # API 客户端
│   │   └── pages/             # 页面组件
│   └── vite.config.ts
├── state/                     # 登录状态文件（不提交 Git）
├── logs/                      # 运行日志
└── data/                      # 数据文件
```

## 🚀 快速开始

### 1. 安装依赖

```bash
# 后端
pip install -r server/requirements.txt
playwright install chromium

# 前端
cd web
npm install
```

### 2. 启动 Web 管理后台

```bash
# 启动后端 API (http://localhost:8000)
python start.py

# 启动前端 (http://localhost:5173)
cd web
npm run dev
```

### 3. CLI 命令行使用

```bash
# 登录（首次或状态过期时）
python main.py login taobao      # 淘宝
python main.py login weixin      # 微信
python main.py login shipinhao   # 视频号
python main.py login doudian     # 抖店
python main.py login 3e3e        # 3e3e

# 批量采集（从桌面 urls.xlsx 读取 URL）
python main.py crawl

# 批量上架
python main.py upload            # 微信小商店
python main.py upload-channels   # 视频号小店
python main.py upload-doudian    # 抖店
```

## 📋 工作流程

```
扫码登录 → 保存状态 → 批量采集商品数据 → 保存到数据库/Excel → 批量上架到各平台
```

**Web 管理后台支持：**
- 在仪表盘查看采集/上架统计和任务状态
- 在商品管理页面浏览已采集商品，双击查看详情
- 创建采集/上架任务，支持立即执行或定时调度
- 在平台管理页面一键触发登录

## 📝 数据格式

### 采集输入：`urls.xlsx`（桌面）
A 列存放商品 URL，每行一个。

### 采集输出
- **数据库**：SQLite（`server/data.db`）
- **Excel**：`taobao_products.xlsx`（桌面）
- **图片**：`桌面/童装/{商品标题}/` 目录下按主图、SKU图分类存放

## ⚠️ 注意事项

- `state/` 目录下的 JSON 文件包含登录凭证，已加入 `.gitignore`，**请勿提交**
- 需要安装 **Microsoft Edge** 浏览器（Chromium 内核）
- 采集频率通过随机延迟控制，避免触发平台风控
- 首次使用各平台功能前，需先完成对应平台的登录

## 📄 License

MIT
