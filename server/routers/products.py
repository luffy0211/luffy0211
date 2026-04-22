from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from server.database import get_db
from server.models import Product

router = APIRouter()


class ProductOut(BaseModel):
    id: int
    title: str
    price: str
    url: str
    style: str
    color: str
    season: str
    material: str
    fabric: str
    safety_level: str
    height: str
    gender: str
    main_images: str
    sku_images: str
    source: str
    status: str
    crawled_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class ProductListOut(BaseModel):
    total: int
    items: list[ProductOut]


@router.get("", response_model=ProductListOut)
async def list_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str = Query("", description="搜索标题"),
    source: str = Query("", description="来源筛选"),
    status: str = Query("", description="状态筛选"),
    db: AsyncSession = Depends(get_db),
):
    query = select(Product)
    count_query = select(func.count(Product.id))

    if search:
        query = query.where(Product.title.contains(search))
        count_query = count_query.where(Product.title.contains(search))
    if source:
        query = query.where(Product.source == source)
        count_query = count_query.where(Product.source == source)
    if status:
        query = query.where(Product.status == status)
        count_query = count_query.where(Product.status == status)

    total = (await db.execute(count_query)).scalar() or 0
    items = (
        await db.execute(
            query.order_by(desc(Product.created_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()

    return ProductListOut(total=total, items=items)


@router.get("/{product_id}", response_model=ProductOut)
async def get_product(product_id: int, db: AsyncSession = Depends(get_db)):
    product = await db.get(Product, product_id)
    if not product:
        raise HTTPException(404, "商品不存在")
    return product


@router.delete("/{product_id}")
async def delete_product(product_id: int, db: AsyncSession = Depends(get_db)):
    product = await db.get(Product, product_id)
    if not product:
        raise HTTPException(404, "商品不存在")
    await db.delete(product)
    await db.commit()
    return {"message": "已删除"}


@router.delete("")
async def batch_delete_products(
    ids: list[int],
    db: AsyncSession = Depends(get_db),
):
    for pid in ids:
        product = await db.get(Product, pid)
        if product:
            await db.delete(product)
    await db.commit()
    return {"message": f"已删除 {len(ids)} 条"}
