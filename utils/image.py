import asyncio
import os
import random
from typing import Optional
from utils.logger import setup_logger

logger = setup_logger("image")

IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"]


def get_images_from_folder(folder_path: str) -> list[str]:
    if not folder_path or not os.path.exists(folder_path):
        return []

    images = []
    if os.path.isdir(folder_path):
        for file in os.listdir(folder_path):
            if os.path.splitext(file)[1].lower() in IMAGE_EXTENSIONS:
                images.append(os.path.abspath(os.path.join(folder_path, file)))
    elif os.path.isfile(folder_path):
        images.append(os.path.abspath(folder_path))

    return sorted(images)


def sanitize_filename(name: str, max_length: int = 50) -> str:
    safe = "".join(c for c in name if c not in r'\/:*?"<>|').strip()
    return safe[:max_length] if safe else "product"


def fix_image_url(src: str, size_replace: Optional[tuple] = None) -> str:
    if not src:
        return ""

    if src.startswith("//img.alicdn.com"):
        pass
    elif src.startswith("//img"):
        src = src.replace("//img", "//img.alicdn.com", 1)

    if "_q50.jpg_.webp" in src:
        src = src.replace("_q50.jpg_.webp", "")
    elif "_q50" in src:
        src = src.split("_q50")[0]

    if size_replace:
        src = src.replace(size_replace[0], size_replace[1])

    if src.startswith("//"):
        src = "https:" + src

    return src


async def download_image(
    session,
    url: str,
    filepath: str,
    headers: dict,
    semaphore: asyncio.Semaphore,
    max_retries: int = 3,
    timeout: int = 15,
) -> bool:
    import aiohttp

    async with semaphore:
        for attempt in range(max_retries):
            try:
                async with session.get(
                    url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=timeout),
                ) as resp:
                    if resp.status == 200:
                        content = await resp.read()
                        os.makedirs(os.path.dirname(filepath), exist_ok=True)
                        with open(filepath, "wb") as f:
                            f.write(content)
                        logger.info(f"已保存: {os.path.basename(filepath)}")
                        return True
                    elif resp.status == 420:
                        delay = (attempt + 1) * 3
                        logger.warning(f"触发反爬(420)，{delay}秒后重试...")
                        await asyncio.sleep(delay)
                    else:
                        logger.warning(f"下载失败 status={resp.status}: {url}")
                        return False
            except Exception as e:
                delay = (attempt + 1) * 2
                logger.warning(f"下载异常(第{attempt+1}次): {e}，{delay}秒后重试")
                await asyncio.sleep(delay)

        logger.error(f"下载最终失败: {url}")
        return False


async def download_images_batch(
    page,
    product_name: str,
    output_root: str,
    selectors: dict,
    headers: dict,
    max_concurrent: int = 3,
) -> dict:
    import aiohttp

    safe_name = sanitize_filename(product_name)
    product_folder = os.path.join(output_root, safe_name)
    sku_folder = os.path.join(product_folder, "cq")
    os.makedirs(product_folder, exist_ok=True)
    os.makedirs(sku_folder, exist_ok=True)

    logger.info(f"图片保存目录: {product_folder}")
    semaphore = asyncio.Semaphore(max_concurrent)
    result = {"main": "", "sku": ""}

    async with aiohttp.ClientSession() as session:
        # 主图
        main_images = await page.query_selector_all(selectors["main_image"])
        main_tasks = []
        main_paths = []

        for i, img in enumerate(main_images):
            src = await img.get_attribute("src")
            url = fix_image_url(src)
            if not url:
                continue
            ext = ".png" if ".png" in url else ".jpg"
            filename = f"{safe_name}_主图_{i+1}{ext}"
            filepath = os.path.join(product_folder, filename)
            main_paths.append(filepath)
            main_tasks.append(download_image(session, url, filepath, headers, semaphore))

        logger.info(f"正在并发下载 {len(main_tasks)} 张主图...")
        main_results = await asyncio.gather(*main_tasks, return_exceptions=True)
        success_main = [p for p, r in zip(main_paths, main_results) if r is True]
        result["main"] = "; ".join(success_main)

        # SKU 图
        sku_images = await page.query_selector_all(selectors["sku_image"])
        sku_tasks = []
        sku_paths = []

        for i, img in enumerate(sku_images):
            src = await img.get_attribute("src")
            url = fix_image_url(src, size_replace=("_30x30", "_200x200"))
            if not url:
                continue
            ext = ".png" if ".png" in url else ".jpg"
            filename = f"{safe_name}_SKU_{i+1}{ext}"
            filepath = os.path.join(sku_folder, filename)
            sku_paths.append(filepath)
            sku_tasks.append(download_image(session, url, filepath, headers, semaphore))

        logger.info(f"正在并发下载 {len(sku_tasks)} 张SKU图...")
        sku_results = await asyncio.gather(*sku_tasks, return_exceptions=True)
        success_sku = [p for p, r in zip(sku_paths, sku_results) if r is True]
        result["sku"] = "; ".join(success_sku)

    logger.info(f"图片下载完成！主图: {len(success_main)}张, SKU: {len(success_sku)}张")
    return result
