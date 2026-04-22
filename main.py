import argparse
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    parser = argparse.ArgumentParser(
        description="电商自动化工具 — 淘宝/天猫采集 + 微信小商店上架",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # login
    login_parser = subparsers.add_parser("login", help="登录并保存状态")
    login_parser.add_argument(
        "platform",
        choices=["taobao", "weixin", "shipinhao", "doudian", "3e3e"],
        help="登录平台: taobao / weixin / shipinhao / doudian / 3e3e",
    )

    # crawl
    subparsers.add_parser("crawl", help="批量采集天猫商品（从桌面 urls.xlsx 读取）")

    # upload
    subparsers.add_parser("upload", help="批量上架到微信小商店（从桌面 影刀上架参数.xlsx 读取）")

    # upload-channels
    subparsers.add_parser("upload-channels", help="批量上架到视频号小店（从桌面 影刀上架参数.xlsx 读取）")

    # upload-doudian
    subparsers.add_parser("upload-doudian", help="批量上架到抖店（从桌面 影刀上架参数.xlsx 读取）")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        print("\n用法示例:")
        print("  python main.py login taobao        # 淘宝登录")
        print("  python main.py login weixin        # 微信登录")
        print("  python main.py login shipinhao     # 视频号登录")
        print("  python main.py login doudian       # 抖店登录")
        print("  python main.py login 3e3e          # 3e3e登录")
        print("  python main.py crawl               # 批量采集")
        print("  python main.py upload              # 批量上架到微信小商店")
        print("  python main.py upload-channels     # 批量上架到视频号小店")
        print("  python main.py upload-doudian      # 批量上架到抖店")
        return

    if args.command == "login":
        if args.platform == "taobao":
            from login.taobao_login import login_and_save_state
            asyncio.run(login_and_save_state())
        elif args.platform == "weixin":
            from login.weixin_login import login_and_save_state
            asyncio.run(login_and_save_state())
        elif args.platform == "shipinhao":
            from login.shipinhao_login import login_and_save_state
            asyncio.run(login_and_save_state())
        elif args.platform == "doudian":
            from login.doudian_login import login_and_save_state
            asyncio.run(login_and_save_state())
        elif args.platform == "3e3e":
            from login.e3e3_login import login_and_save_state
            asyncio.run(login_and_save_state())

    elif args.command == "crawl":
        from crawler.tmall_crawler import run_crawler
        asyncio.run(run_crawler())

    elif args.command == "upload":
        from uploader.weixin_uploader import run_uploader
        asyncio.run(run_uploader())

    elif args.command == "upload-channels":
        from uploader.shipinhao_uploader import run_uploader
        asyncio.run(run_uploader())

    elif args.command == "upload-doudian":
        from uploader.doudian_uploader import run_uploader
        asyncio.run(run_uploader())


if __name__ == "__main__":
    main()
