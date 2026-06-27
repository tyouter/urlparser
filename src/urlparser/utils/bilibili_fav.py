"""
B站收藏夹 CLI 工具 — 绕过 412 反爬

用法:
    # 列出所有收藏夹
    python -m urlparser.utils.bilibili_fav list --uid 14180438

    # 获取某个收藏夹的视频列表
    python -m urlparser.utils.bilibili_fav resources <media_id> --uid 14180438

    # 压力测试：连续 N 次调用验证无 412
    python -m urlparser.utils.bilibili_fav stress <media_id> --count 20
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List

import requests


def load_cookies(platform: str = "bilibili") -> Dict[str, str]:
    """加载 Cookie 文件"""
    cookies_dir = Path(os.path.expanduser("~")) / ".urlparser" / "cookies"
    cookie_file = cookies_dir / f"{platform}_cookies.json"
    if not cookie_file.exists():
        raise FileNotFoundError(f"Cookie 文件不存在: {cookie_file}")
    with open(cookie_file, encoding="utf-8") as f:
        data = json.load(f)
    return {c["name"]: c["value"] for c in data if "name" in c and "value" in c}


def make_session() -> requests.Session:
    """创建带 Cookie 和正确 Headers 的 Session"""
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.bilibili.com/",
        "Origin": "https://www.bilibili.com",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    })
    cookies = load_cookies("bilibili")
    for name, value in cookies.items():
        session.cookies.set(name, value, domain=".bilibili.com")
    return session


def cmd_list(args):
    """列出所有收藏夹"""
    from urlparser.utils.bilibili_wbi import get_mixin_key

    session = make_session()
    resp = session.get(
        "https://api.bilibili.com/x/v3/fav/folder/created/list-all",
        params={"up_mid": args.uid},
    )
    data = resp.json()
    if data.get("code") != 0:
        print(f"❌ 收藏夹列表失败: {data.get('message')}", file=sys.stderr)
        sys.exit(1)

    folders = data["data"]["list"]
    print(f"📁 {len(folders)} 个收藏夹:\n")
    for f in folders:
        print(f"  [{f['id']}] {f['title']} — {f.get('media_count', 0)} 个内容")
    return folders


def cmd_resources(args):
    """获取收藏夹视频列表"""
    from urlparser.utils.bilibili_wbi import iter_fav_resource_list

    session = make_session()
    total = 0
    for items, pn, has_more in iter_fav_resource_list(
        session, args.media_id, delay=args.delay
    ):
        for item in items:
            bv = item["bvid"]
            title = item["title"]
            print(f"  [{pn}] {bv} {title}")
            total += 1
        if not has_more:
            break
        if args.max_pages and pn >= args.max_pages:
            break
    print(f"\n✅ 共 {total} 条")


def cmd_stress(args):
    """压力测试: 连续 N 次调用验证无 412"""
    from urlparser.utils.bilibili_wbi import fetch_fav_resource_list

    session = make_session()
    media_id = args.media_id
    count = args.count
    delay = args.delay

    print(f"🧪 压力测试: {count} 次连续调用 resource/list?media_id={media_id}&pn=1&ps=20")
    print(f"   页间延时: {delay}s\n")

    success = 0
    fail_412 = 0
    fail_other = 0
    errors = []

    t_start = time.time()
    for i in range(count):
        try:
            items, has_more = fetch_fav_resource_list(
                session, media_id, pn=1, ps=20
            )
            success += 1
            status = "✅"
            msg = f"{len(items)} items, has_more={has_more}"
        except RuntimeError as e:
            msg = str(e)[:100]
            if "412" in msg:
                fail_412 += 1
                status = "🔴 412"
            else:
                fail_other += 1
                status = "⚠️"
            errors.append((i + 1, msg))
        except Exception as e:
            fail_other += 1
            status = "❌"
            msg = str(e)[:100]
            errors.append((i + 1, msg))

        print(f"  [{i+1:3d}/{count}] {status} {msg}")

        if i < count - 1 and delay > 0:
            time.sleep(delay)

    elapsed = time.time() - t_start
    print(f"\n{'='*60}")
    print(f"📊 结果: {success}/{count} 成功, {fail_412} 次412, {fail_other} 次其他错误")
    print(f"⏱  耗时: {elapsed:.1f}s ({elapsed/count:.2f}s/次)")
    if errors:
        print(f"\n❌ 错误详情:")
        for idx, err in errors[:10]:
            print(f"  第{idx}次: {err}")

    # 返回码: 全部成功=0, 有失败=1
    sys.exit(0 if success == count else 1)


def main():
    parser = argparse.ArgumentParser(
        description="B站收藏夹工具 — 绕过 412 反爬 (WBI 签名 + 请求头强化)",
    )
    parser.add_argument(
        "--uid", default="14180438",
        help="B站用户 UID (默认: 14180438)",
    )

    sub = parser.add_subparsers(dest="cmd")

    # list
    p_list = sub.add_parser("list", help="列出所有收藏夹")
    p_list.set_defaults(func=cmd_list)

    # resources
    p_res = sub.add_parser("resources", help="获取收藏夹视频列表")
    p_res.add_argument("media_id", help="收藏夹 ID")
    p_res.add_argument("--max-pages", type=int, default=0, help="最大页数 (0=全部)")
    p_res.add_argument("--delay", type=float, default=0.5, help="页间延时秒数")
    p_res.set_defaults(func=cmd_resources)

    # stress
    p_stress = sub.add_parser("stress", help="压力测试: 连续N次调用验证无412")
    p_stress.add_argument("media_id", help="收藏夹 ID (用于测试)")
    p_stress.add_argument("--count", type=int, default=20, help="调用次数 (默认: 20)")
    p_stress.add_argument("--delay", type=float, default=0.3, help="调用间延时秒数")
    p_stress.set_defaults(func=cmd_stress)

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
