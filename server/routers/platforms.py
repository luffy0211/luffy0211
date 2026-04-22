import os
import sys
import asyncio
import threading
import importlib
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional
from server.database import get_db
from server.models import Platform
from config import STATE_DIR

router = APIRouter()

STATE_FILE_MAP = {
    "taobao": "taobao_state.json",
    "weixin": "weixin_state.json",
    "shipinhao": "shipinhao_state.json",
    "xhs": "xiaohongshu_state.json",
    "doudian": "doudian_state.json",
    "qianniu": "qianniu_state.json",
    "3e3e": "3e3e_state.json",
}


class PlatformOut(BaseModel):
    id: int
    name: str
    code: str
    login_active: bool
    last_login: Optional[datetime]

    model_config = {"from_attributes": True}


def _run_login_in_thread(module_path: str):
    """在新线程中用 ProactorEventLoop 运行登录（Windows 需要子进程支持）"""
    def _target():
        if sys.platform.startswith("win"):
            loop = asyncio.ProactorEventLoop()
        else:
            loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            module = importlib.import_module(module_path)
            loop.run_until_complete(module.login_and_save_state())
        finally:
            loop.close()

    t = threading.Thread(target=_target, daemon=True)
    t.start()


@router.get("", response_model=list[PlatformOut])
async def list_platforms(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Platform))
    platforms = result.scalars().all()

    for p in platforms:
        state_file = os.path.join(STATE_DIR, STATE_FILE_MAP.get(p.code, ""))
        p.login_active = os.path.exists(state_file) and os.path.getsize(state_file) > 10

    await db.commit()
    return platforms


@router.post("/{code}/login")
async def trigger_login(code: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Platform).where(Platform.code == code))
    platform = result.scalars().first()
    if not platform:
        raise HTTPException(404, "平台不存在")

    login_map = {
        "taobao": "login.taobao_login",
        "weixin": "login.weixin_login",
        "shipinhao": "login.shipinhao_login",
        "doudian": "login.doudian_login",
        "qianniu": "login.qianniu_login",
        "3e3e": "login.e3e3_login",
    }

    module_path = login_map.get(code)
    if not module_path:
        raise HTTPException(400, f"暂不支持 {code} 登录")

    _run_login_in_thread(module_path)

    platform.last_login = datetime.now()
    await db.commit()

    return {"message": f"{platform.name} 登录已启动，请在弹出的浏览器中完成扫码"}
