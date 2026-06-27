"""
B站 WBI 签名工具

B站 部分 API 端点（如 fav/resource/list）需要 WBI 签名参数 (w_rid + wts)，
否则返回 HTTP 412。本模块提供签名生成和便捷请求方法。

用法:
    from urlparser.utils.bilibili_wbi import sign_params, get_mixin_key, fetch_fav_resource_list

    # 方式1: 手动签名
    mixin_key = get_mixin_key(session)  # session 是 requests.Session
    params = sign_params({"media_id": "123", "pn": 1, "ps": 20, "platform": "web"}, mixin_key)
    resp = session.get("https://api.bilibili.com/x/v3/fav/resource/list", params=params)

    # 方式2: 一行搞定
    items, has_more = fetch_fav_resource_list(session, media_id="123", pn=1, ps=20)
"""

import hashlib
import time
import urllib.parse
from typing import Dict, List, Tuple, Optional

import requests

# WBI 混肴密钥索引表 — 从 img_key + sub_key (各32字符,共64字符) 中选取32字符
_MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
    27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
]


def _extract_key_from_url(url: str) -> str:
    """从 WBI 图片 URL 中提取密钥（文件名去掉扩展名）"""
    filename = url.rsplit("/", 1)[-1]
    return filename.split(".")[0]


def get_mixin_key(session: requests.Session) -> str:
    """获取当前有效的 WBI mixin key

    调用 nav API 获取 img_key 和 sub_key，混肴后返回 mixin_key。
    mixin_key 有效期约 1 小时，过期后需重新获取。

    Args:
        session: 已登录的 requests.Session (需包含 bilibili Cookie)

    Returns:
        32 字符的 mixin_key

    Raises:
        RuntimeError: API 返回异常
    """
    resp = session.get(
        "https://api.bilibili.com/x/web-interface/nav",
        headers={"Referer": "https://www.bilibili.com/"},
        timeout=15,
    )
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"nav API 失败: {data.get('message', '未知错误')}")

    wbi_img = data["data"]["wbi_img"]
    img_key = _extract_key_from_url(wbi_img["img_url"])
    sub_key = _extract_key_from_url(wbi_img["sub_url"])

    raw = img_key + sub_key  # 64 字符
    return "".join(raw[i] for i in _MIXIN_KEY_ENC_TAB)


def sign_params(params: Dict, mixin_key: str) -> Dict:
    """为请求参数添加 WBI 签名

    修改传入字典（添加 wts 和 w_rid），同时返回该字典。
    如果 params 已经包含 w_rid/wts，则跳过签名（幂等）。

    Args:
        params: 请求参数字典
        mixin_key: 32 字符的 mixin key

    Returns:
        添加了 wts 和 w_rid 的参数字典（原地修改）
    """
    if "w_rid" in params:
        return params  # 已经签名

    params["wts"] = int(time.time())
    # 按 key 字母序排序，构建 query string
    sorted_items = sorted(params.items(), key=lambda x: x[0])
    query_string = urllib.parse.urlencode(sorted_items)
    w_rid = hashlib.md5((query_string + mixin_key).encode()).hexdigest()
    params["w_rid"] = w_rid
    return params


def fetch_fav_resource_list(
    session: requests.Session,
    media_id: str,
    pn: int = 1,
    ps: int = 20,
    *,
    mixin_key: Optional[str] = None,
    keyword: str = "",
    order: str = "mtime",
    tid: int = 0,
    platform: str = "web",
) -> Tuple[List[Dict], bool]:
    """获取 B站 收藏夹视频列表（带 WBI 签名，绕过 412）

    单次调用获取一页数据。如需遍历整个收藏夹，在外层循环中调用。

    Args:
        session: 已登录的 requests.Session
        media_id: 收藏夹 ID
        pn: 页码（从 1 开始）
        ps: 每页数量（最大 20）
        mixin_key: WBI mixin key。为 None 时自动获取（首次调用较慢）
        keyword: 搜索关键词（可选）
        order: 排序方式 (mtime=最近收藏, view=最多播放, pubtime=最新投稿)
        tid: 分类 ID (0=全部)
        platform: 平台标识 (web/android/ios)

    Returns:
        (items, has_more) 元组:
        - items: [{"bvid": "BV...", "title": "...", ...}, ...]
        - has_more: 是否还有下一页

    Raises:
        RuntimeError: API 返回错误
    """
    if mixin_key is None:
        mixin_key = get_mixin_key(session)

    params = {
        "media_id": media_id,
        "pn": pn,
        "ps": min(ps, 20),
        "platform": platform,
    }
    if keyword:
        params["keyword"] = keyword
    if order and order != "mtime":
        params["order"] = order
    if tid:
        params["tid"] = tid

    params = sign_params(params, mixin_key)

    resp = session.get(
        "https://api.bilibili.com/x/v3/fav/resource/list",
        params=params,
        timeout=30,
    )

    # 412 或其他非 200 状态码
    if resp.status_code != 200:
        raise RuntimeError(
            f"resource/list HTTP {resp.status_code}: "
            f"{resp.text[:300] if resp.text else '(empty body)'}"
        )

    try:
        data = resp.json()
    except Exception as e:
        raise RuntimeError(f"resource/list 非 JSON 响应: {e}")

    if data.get("code") != 0:
        raise RuntimeError(f"resource/list API 错误: {data.get('message', '未知')}")

    medias = data.get("data", {}).get("medias", [])
    has_more = data.get("data", {}).get("has_more", False)

    items = []
    for m in medias:
        if not isinstance(m, dict):
            continue
        items.append({
            "bvid": m.get("bvid", ""),
            "title": m.get("title", ""),
            "cover": m.get("cover", ""),
            "intro": m.get("intro", ""),
            "duration": m.get("duration", 0),
            "pubdate": m.get("pubdate", 0),
            "upper": m.get("upper", {}).get("name", "") if isinstance(m.get("upper"), dict) else "",
            "cnt_info": m.get("cnt_info", {}),
            "link": m.get("link", ""),
            "page": m.get("page", 1),
            "type": m.get("type", 2),  # 2=视频
            "id": m.get("id", 0),      # 收藏内容 ID (avid)
        })
    return items, has_more


def iter_fav_resource_list(
    session: requests.Session,
    media_id: str,
    *,
    ps: int = 20,
    max_pages: int = 0,
    delay: float = 0.5,
    **kwargs,
):
    """遍历 B站 收藏夹全部视频（生成器，带翻页和延时）

    Args:
        session: 已登录的 requests.Session
        media_id: 收藏夹 ID
        ps: 每页数量
        max_pages: 最大页数 (0=不限制)
        delay: 页间延时（秒），避免触发频率限制
        **kwargs: 传递给 fetch_fav_resource_list 的其他参数

    Yields:
        (items, page_num, has_more) 元组 — 每页的视频列表
    """
    mixin_key = get_mixin_key(session)
    pn = 1
    while True:
        if max_pages and pn > max_pages:
            break

        items, has_more = fetch_fav_resource_list(
            session, media_id, pn=pn, ps=ps, mixin_key=mixin_key, **kwargs
        )
        yield items, pn, has_more

        if not has_more:
            break

        pn += 1
        if delay > 0:
            time.sleep(delay)
