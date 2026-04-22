import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.db")
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def init_db():
    from server.models import Product, Task, TaskItem, Platform
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        from sqlalchemy import select
        result = await session.execute(select(Platform))
        if not result.scalars().first():
            defaults = [
                Platform(name="淘宝/天猫", code="taobao", login_active=False),
                Platform(name="微信小商店", code="weixin", login_active=False),
                Platform(name="视频号小店", code="shipinhao", login_active=False),
                Platform(name="小红书", code="xhs", login_active=False),
                Platform(name="抖店", code="doudian", login_active=False),
                Platform(name="千牛", code="qianniu", login_active=False),
                Platform(name="3e3e", code="3e3e", login_active=False),
            ]
            session.add_all(defaults)
            await session.commit()
        else:
            existing = await session.execute(select(Platform).where(Platform.code == "3e3e"))
            if not existing.scalars().first():
                session.add(Platform(name="3e3e", code="3e3e", login_active=False))
                await session.commit()


async def get_db():
    async with async_session() as session:
        yield session
