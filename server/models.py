from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, Boolean, DateTime, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from server.database import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(500), default="")
    price: Mapped[str] = mapped_column(String(50), default="")
    url: Mapped[str] = mapped_column(String(2000), default="")
    style: Mapped[str] = mapped_column(String(200), default="")
    color: Mapped[str] = mapped_column(String(500), default="")
    season: Mapped[str] = mapped_column(String(200), default="")
    material: Mapped[str] = mapped_column(String(500), default="")
    fabric: Mapped[str] = mapped_column(String(200), default="")
    safety_level: Mapped[str] = mapped_column(String(100), default="")
    height: Mapped[str] = mapped_column(String(200), default="")
    gender: Mapped[str] = mapped_column(String(100), default="")
    main_images: Mapped[str] = mapped_column(Text, default="")
    sku_images: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(50), default="tmall")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    crawled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    task_items: Mapped[list["TaskItem"]] = relationship(back_populates="product")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type: Mapped[str] = mapped_column(String(20))  # crawl / upload
    status: Mapped[str] = mapped_column(String(20), default="pending")
    schedule_type: Mapped[str] = mapped_column(String(20), default="immediate")
    cron_expr: Mapped[str] = mapped_column(String(100), default="")
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    config_json: Mapped[str] = mapped_column(Text, default="{}")
    result_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    items: Mapped[list["TaskItem"]] = relationship(back_populates="task", cascade="all, delete-orphan")


class TaskItem(Base):
    __tablename__ = "task_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"))
    product_id: Mapped[Optional[int]] = mapped_column(ForeignKey("products.id"), nullable=True)
    platform: Mapped[str] = mapped_column(String(50), default="")
    url: Mapped[str] = mapped_column(String(2000), default="")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    error_msg: Mapped[str] = mapped_column(Text, default="")

    task: Mapped["Task"] = relationship(back_populates="items")
    product: Mapped[Optional["Product"]] = relationship(back_populates="task_items")


class Platform(Base):
    __tablename__ = "platforms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100))
    code: Mapped[str] = mapped_column(String(50), unique=True)
    login_active: Mapped[bool] = mapped_column(Boolean, default=False)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
