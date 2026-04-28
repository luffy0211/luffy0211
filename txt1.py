import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from utils.browser import launch_browser, create_context
from config import DOUDIAN_STATE_FILE, BROWSER_CHANNEL

HOMEPAGE_URL = "https://fxg.jinritemai.com/ffa/mshop/homepage/index"
TRACKING_HISTORY_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "txt1_seen_tracking_numbers.txt",
)


def load_seen_tracking_numbers() -> set[str]:
    if not os.path.exists(TRACKING_HISTORY_FILE):
        return set()

    with open(TRACKING_HISTORY_FILE, "r", encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


def save_new_tracking_number(tracking_number: str) -> None:
    with open(TRACKING_HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(f"{tracking_number}\n")


async def click_view_logistics(status) -> None:
    """从当前'已发货'状态出发，定位同一行或同一订单块中的'查看物流'。"""
    candidates = [
        status.locator("xpath=ancestor::tr[1]//a[normalize-space()='查看物流']").first,
        status.locator("xpath=ancestor::tbody[1]//a[normalize-space()='查看物流']").first,
        status.locator(
            "xpath=ancestor::*[contains(@class,'auxo-table-row')][1]//a[normalize-space()='查看物流']"
        ).first,
    ]

    last_error = None
    for link in candidates:
        try:
            if await link.count() == 0:
                continue
            await link.wait_for(state="visible", timeout=3000)
            await link.scroll_into_view_if_needed()
            await link.click(timeout=10000)
            return
        except Exception as e:
            last_error = e

    raise PlaywrightTimeoutError(
        f"未找到当前'已发货'记录对应的'查看物流'按钮: {last_error}"
    )


async def process_current_page(
    page,
    seen_tracking_numbers: set[str],
    current_run_new_tracking_numbers: list[str],
) -> int:
    """处理当前页所有'已发货'订单，返回本页去重后新增的物流单号数量"""
    index = 0
    new_count = 0

    while True:
        shipped_statuses = page.locator(
            "xpath=//td[contains(@class,'auxo-table-cell')]//div/span[normalize-space()='已发货']"
        )
        total = await shipped_statuses.count()

        if index >= total:
            break

        status = shipped_statuses.nth(index)
        await status.scroll_into_view_if_needed()
        await asyncio.sleep(0.5)

        try:
            await click_view_logistics(status)
            await asyncio.sleep(2)
        except Exception as e:
            print(f"[{index + 1}] 点击查看物流失败: {e}")
            index += 1
            continue

        try:
            tracking_span = page.locator(
                'xpath=//td[normalize-space()="物流单号"]/following-sibling::td//span'
            ).first
            await tracking_span.wait_for(state="visible", timeout=10000)
            tracking_number = (await tracking_span.text_content() or "").strip()
            if not tracking_number:
                print(f"[{index + 1}] 物流单号为空")
            elif tracking_number in seen_tracking_numbers:
                print(f"[{index + 1}] 物流单号已输出过，已跳过: {tracking_number}")
            else:
                seen_tracking_numbers.add(tracking_number)
                current_run_new_tracking_numbers.append(tracking_number)
                save_new_tracking_number(tracking_number)
                new_count += 1
                print(f"[{index + 1}] 物流单号: {tracking_number}")
        except Exception as e:
            print(f"[{index + 1}] 获取物流单号失败: {e}")

        try:
            confirm_btn = page.locator(
                'xpath=//button[contains(@class,"auxo-btn-primary") and .//span[normalize-space()="确定"]]'
            ).first
            await confirm_btn.wait_for(state="visible", timeout=5000)
            await confirm_btn.click()
            await confirm_btn.wait_for(state="hidden", timeout=5000)
            await asyncio.sleep(1)
        except Exception as e:
            print(f"[{index + 1}] 关闭弹窗失败: {e}")

        index += 1

    return new_count


async def main():
    async with async_playwright() as p:
        browser = await launch_browser(p, channel=BROWSER_CHANNEL)
        context = await create_context(
            browser, state_file=DOUDIAN_STATE_FILE, no_viewport=True
        )
        page = await context.new_page()

        await page.goto(HOMEPAGE_URL, wait_until="domcontentloaded")
        await asyncio.sleep(3)

        order_link = page.locator('xpath=(//a[text()="订单管理"])[1]')
        await order_link.wait_for(state="visible", timeout=15000)
        await order_link.click()
        print("已点击订单管理")
        await asyncio.sleep(3)

        filter_btn = page.locator('xpath=//span[text()="24h需发货及揽收"]')
        await filter_btn.wait_for(state="visible", timeout=15000)
        await filter_btn.click()
        print("已点击 24h需发货及揽收")
        await asyncio.sleep(3)

        page_num = 1
        total_count = 0
        seen_tracking_numbers = load_seen_tracking_numbers()
        current_run_new_tracking_numbers = []

        print(f"已加载历史物流单号 {len(seen_tracking_numbers)} 条")

        while True:
            print(f"\n--- 第 {page_num} 页 ---")
            count = await process_current_page(
                page, seen_tracking_numbers, current_run_new_tracking_numbers
            )
            total_count += count
            print(f"第 {page_num} 页新增 {count} 条，本次运行累计新增 {total_count} 条")

            next_btn = page.locator(
                'xpath=//li[@title="下一页" and not(contains(@class,"disabled"))]/button'
            )
            if await next_btn.count() > 0 and await next_btn.first.is_visible(timeout=3000):
                await next_btn.first.click()
                print("翻到下一页...")
                await asyncio.sleep(3)
                page_num += 1
            else:
                print("已到最后一页")
                break

        print(f"\n全部完成，本次新增 {total_count} 条物流单号")
        if current_run_new_tracking_numbers:
            print("\n本次新增的物流单号：")
            for idx, tracking_number in enumerate(current_run_new_tracking_numbers, start=1):
                print(f"{idx}. {tracking_number}")
        else:
            print("\n本次没有新增物流单号")

        try:
            while True:
                await asyncio.sleep(1)
                if page.is_closed():
                    break
        except Exception:
            pass

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
