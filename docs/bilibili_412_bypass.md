# auto_inbox.py 集成指南 — B站 412 绕过

## 方案概述

根因: B站 `resource/list` 端点需要 **WBI 签名** (`w_rid` + `wts` 参数) 才能绕过高防 WAF，
否则返回 HTTP 412。`list-all` 端点不需要签名所以一直正常。

解决方案已实现在 urlparser 中：
- `urlparser.utils.bilibili_wbi` — WBI 签名工具 + 便捷函数
- `urlparser.utils.bilibili_fav` — CLI 压力测试工具

## auto_inbox.py 需要改 2 处

### 改动 1: 文件顶部 import (在 `import requests` 之后加)

```python
import requests

# B站 WBI 签名（绕过 resource/list 的 412 反爬）
from urlparser.utils.bilibili_wbi import iter_fav_resource_list, fetch_fav_resource_list
```

### 改动 2: 替换 make_session() (原 L104-112)

在 `session.headers.update()` 中添加 `Referer` 和 `Origin`：

```python
def make_session(platform: str) -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": f"https://www.{platform}.com/",
        "Origin": f"https://www.{platform}.com",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    })
    cookies = load_cookies(platform)
    for name, value in cookies.items():
        session.cookies.set(name, value, domain=f".{platform}.com")
    return session
```

### 改动 3: 替换 fetch_bilibili() (原 L116-164)

```python
def fetch_bilibili(session: requests.Session) -> List[dict]:
    """拉B站收藏夹，返回 [{platform, source, title, url, tags}, ...]
    
    使用 WBI 签名绕过 resource/list 的 412 反爬。
    """
    items = []
    resp = session.get("https://api.bilibili.com/x/v3/fav/folder/created/list-all",
                       params={"up_mid": BILIBILI_UID})
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"B站收藏夹列表失败: {data.get('message')}")

    folders = data["data"]["list"]
    print(f"  B站: {len(folders)} 个收藏夹")

    for folder in folders:
        folder_title = folder["title"]
        folder_id = folder["id"]
        try:
            count = 0
            for res_items, pn, has_more in iter_fav_resource_list(
                session, str(folder_id), ps=20, delay=0.5
            ):
                for m in res_items:
                    bv = m.get("bvid", "")
                    if bv:
                        items.append({
                            "platform": "bilibili",
                            "source": f'收藏夹「{folder_title}」',
                            "title": m.get("title", "无标题"),
                            "url": f"https://www.bilibili.com/video/{bv}",
                            "tags": [],
                        })
                        count += 1
                if not has_more:
                    break
            print(f"    📁 {folder_title} {count} 条")
        except Exception as e:
            print(f"    📁 {folder_title} ❌ {e}")
    return items
```

## 验证方法

```bash
# 在 urlparser 虚拟环境中运行压力测试
cd D:\Hermes\projects\urlparser
python -m urlparser.utils.bilibili_fav stress <收藏夹ID> --count 20 --delay 0.3

# 例如 (先用 list 命令查看收藏夹列表)
python -m urlparser.utils.bilibili_fav list --uid 14180438
python -m urlparser.utils.bilibili_fav stress 123456 --count 20
```

## 原理

1. 调用 `nav` API 获取 `img_key` + `sub_key`
2. 混肴生成 32 字符 `mixin_key`
3. 每次请求 `resource/list` 时:
   - 添加 `wts` = 当前 Unix 时间戳
   - 参数按 key 排序后计算 MD5(query_string + mixin_key) → `w_rid`
4. 同时带上 `Referer` + `Origin` 头
5. 页间 0.5s 延时防止频率限制
