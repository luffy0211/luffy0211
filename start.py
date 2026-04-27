"""
一键启动后端服务
用法: python start.py
"""
import sys
import os
import asyncio

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn

if __name__ == "__main__":
    print("=" * 50)
    print("  电商自动化管理系统")
    print("  后端: http://localhost:8000")
    print("  API 文档: http://localhost:8000/docs")
    print("=" * 50)
    port = int(os.getenv("LUFFY_PORT", "8000"))
    uvicorn.run(
        "server.app:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        loop="asyncio",
    )
