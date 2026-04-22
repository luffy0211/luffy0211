import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from server.database import init_db
from server.routers import products, tasks, platforms, dashboard


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    from server.services.scheduler_service import scheduler
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="电商自动化管理系统", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dashboard.router, prefix="/api/dashboard", tags=["仪表盘"])
app.include_router(products.router, prefix="/api/products", tags=["商品"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["任务"])
app.include_router(platforms.router, prefix="/api/platforms", tags=["平台"])


@app.get("/api/health")
async def health():
    return {"status": "ok"}
