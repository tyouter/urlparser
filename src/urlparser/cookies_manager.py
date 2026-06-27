"""
Cookie 交互式获取工具

使用 Playwright 打开浏览器，让用户手动登录，
然后自动保存 cookie 状态到本地文件。

比 browser_cookie3 更可靠：
- 不需要管理员权限
- 支持所有浏览器
- Cookie 直接以 Playwright 格式保存

用法:
    python -m urlparser.cookies_manager login xiaohongshu
    python -m urlparser.cookies_manager status
    python -m urlparser.cookies_manager refresh xiaohongshu
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional


def _get_cookies_dir() -> Path:
    user_dir = Path(os.path.expanduser("~")) / ".urlparser" / "cookies"
    src_dir = Path(__file__).parent.parent.parent / "cookies"
    if src_dir.exists() and any(src_dir.glob("*_cookies.json")):
        if not user_dir.exists() or not any(user_dir.glob("*_cookies.json")):
            import shutil
            user_dir.mkdir(parents=True, exist_ok=True)
            for f in src_dir.glob("*_cookies.json"):
                shutil.copy2(f, user_dir / f.name)
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


COOKIES_DIR = _get_cookies_dir()

PLATFORM_DOMAINS: Dict[str, str] = {
    "xiaohongshu": ".xiaohongshu.com",
    "zhihu": ".zhihu.com",
    "bilibili": ".bilibili.com",
    "weixin": ".weixin.qq.com",
    "youtube": ".youtube.com",
    "github": ".github.com",
    "sspai": ".sspai.com",
}

PLATFORM_LOGIN_URLS: Dict[str, str] = {
    "xiaohongshu": "https://www.xiaohongshu.com",
    "zhihu": "https://www.zhihu.com/signin",
    "bilibili": "https://passport.bilibili.com/login",
    "weixin": "https://mp.weixin.qq.com",
    "youtube": "https://accounts.google.com/login",
    "github": "https://github.com/login",
    "sspai": "https://sspai.com",
}

PROFILES_DIR = Path(os.path.expanduser("~")) / ".urlparser" / "profiles"

# refresh_from_profile 时 goto 的平台首页（已登录态会在首页体现）
PLATFORM_HOME_URLS: Dict[str, str] = {
    "xiaohongshu": "https://www.xiaohongshu.com",
    "zhihu": "https://www.zhihu.com",
    "bilibili": "https://www.bilibili.com",
    "weixin": "https://mp.weixin.qq.com",
    "youtube": "https://www.youtube.com",
    "github": "https://github.com",
    "sspai": "https://sspai.com",
}

# 判定平台 session 是否存活的登录态 cookie 字段（命中任一即视为已登录）
# 仅取"登录态独有"字段；a1/logged_in 这类访客也有的不能用作判定，否则会把访客误判为已登录
_LOGIN_COOKIE_KEYS: Dict[str, List[str]] = {
    "xiaohongshu": ["web_session"],
    "zhihu": ["z_c0"],
    "bilibili": ["SESSDATA", "DedeUserID"],
    "youtube": ["SAPISID", "SID"],
    "github": ["user_session"],
}

_COOKIE_MAX_AGE = 86400 * 7


class CookieManager:
    _max_age_seconds: float = _COOKIE_MAX_AGE  # 可被 configure_max_age 覆盖

    @classmethod
    def configure_max_age(cls, hours: float):
        """设置 cookie 过期阈值（小时），全局生效"""
        cls._max_age_seconds = hours * 3600

    def __init__(self, cookies_dir: Optional[str] = None):
        self.cookies_dir = Path(cookies_dir) if cookies_dir else COOKIES_DIR
        self.cookies_dir.mkdir(parents=True, exist_ok=True)

    def get_cookies_path(self, platform: str) -> Path:
        return self.cookies_dir / f"{platform}_cookies.json"

    def get_cookies(self, platform: str) -> List[Dict]:
        cookies_path = self.get_cookies_path(platform)

        if self._is_valid(cookies_path):
            return self._load_file(cookies_path)

        refreshed = self._refresh_from_browser(platform)
        if refreshed:
            return refreshed

        if cookies_path.exists():
            return self._load_file(cookies_path)

        return []

    def _is_valid(self, path: Path) -> bool:
        if not path.exists():
            return False
        try:
            stat = path.stat()
            age = time.time() - stat.st_mtime
            if age > CookieManager._max_age_seconds:
                return False
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not isinstance(data, list) or len(data) == 0:
                return False
            return True
        except Exception:
            return False

    def _load_file(self, path: Path) -> List[Dict]:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []

    def _refresh_from_browser(self, platform: str) -> Optional[List[Dict]]:
        domain = PLATFORM_DOMAINS.get(platform)
        if not domain:
            return None

        try:
            import browser_cookie3
        except ImportError:
            return None

        cookies = []
        for browser_fn in [browser_cookie3.chrome, browser_cookie3.edge, browser_cookie3.firefox]:
            try:
                cj = browser_fn(domain_name=domain)
                for c in cj:
                    cookies.append({
                        "name": c.name,
                        "value": c.value,
                        "domain": c.domain,
                        "path": c.path,
                        "secure": c.secure,
                    })
                if cookies:
                    break
            except Exception:
                continue

        if cookies:
            self._save_file(self.get_cookies_path(platform), cookies)
            return cookies

        return None

    def _save_file(self, path: Path, cookies: List[Dict]):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(cookies, f, indent=2, ensure_ascii=False)

    def get_profile_path(self, platform: str) -> Path:
        return PROFILES_DIR / platform

    def _clear_profile_lock(self, platform: str):
        """清理 chromium 孤儿锁文件（login/refresh 异常退出后的残留）。

        专用 profile 串行使用前提下安全：避免下次 launch_persistent_context
        因残留 SingletonLock 启动隔离实例、读不到持久化的登录 cookie。
        """
        profile = self.get_profile_path(platform)
        for lock_name in ('SingletonLock', 'SingletonCookie', 'SingletonSocket'):
            lock_file = profile / lock_name
            if lock_file.exists():
                try:
                    lock_file.unlink()
                except Exception:
                    pass

    @staticmethod
    def _extract_cookies(state: dict) -> List[Dict]:
        cookies = []
        for c in state.get('cookies', []):
            cookies.append({
                "name": c['name'],
                "value": c['value'],
                "domain": c['domain'],
                "path": c.get('path', '/'),
                "secure": c.get('secure', False),
                "httpOnly": c.get('httpOnly', False),
                "sameSite": c.get('sameSite', 'Lax'),
                "expires": c.get('expires', -1),
            })
        return cookies

    @staticmethod
    def _has_login_state(platform: str, cookies: List[Dict]) -> bool:
        keys = _LOGIN_COOKIE_KEYS.get(platform)
        if not keys:
            return len(cookies) > 0
        names = {c.get('name') for c in cookies}
        return any(k in names for k in keys)

    def _save_storage(self, path: Path, state: dict):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2, ensure_ascii=False)

    async def refresh_from_profile(self, platform: str) -> Optional[List[Dict]]:
        """从持久化 profile 无扫码读取最新登录态。

        profile 内 session 存活时，headless 重启该 profile，读取 storage_state，
        判定登录态并导出 cookies/storage 文件。session 失效或无 profile 返回 None。
        """
        profile_path = self.get_profile_path(platform)
        if not profile_path.exists():
            return None
        self._clear_profile_lock(platform)
        home_url = PLATFORM_HOME_URLS.get(platform)
        if not home_url:
            return None
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return None

        try:
            async with async_playwright() as p:
                ctx = await p.chromium.launch_persistent_context(
                    user_data_dir=str(profile_path),
                    headless=True,
                    args=['--no-sandbox', '--disable-dev-shm-usage',
                          '--disable-blink-features=AutomationControlled'],
                    viewport={'width': 1280, 'height': 800},
                    locale='zh-CN',
                )
                try:
                    page = ctx.pages[0] if ctx.pages else await ctx.new_page()
                    try:
                        await page.goto(home_url, timeout=30000, wait_until='domcontentloaded')
                    except Exception:
                        pass
                    await page.wait_for_timeout(1500)
                    state = await ctx.storage_state()
                finally:
                    await ctx.close()
        except Exception:
            return None

        cookies = self._extract_cookies(state)
        if not self._has_login_state(platform, state.get('cookies', [])):
            return None

        self._save_file(self.get_cookies_path(platform), cookies)
        self._save_storage(self.cookies_dir / f"{platform}_storage.json", state)
        return cookies

    async def interactive_login(self, platform: str):
        from playwright.async_api import async_playwright

        login_url = PLATFORM_LOGIN_URLS.get(platform)
        if not login_url:
            print(f"Unknown platform: {platform}")
            return False

        profile_path = self.get_profile_path(platform)
        profile_path.mkdir(parents=True, exist_ok=True)
        self._clear_profile_lock(platform)

        print(f"Opening browser for {platform} login...")
        print(f"Login state will persist to profile: {profile_path}")
        print(f"Please log in, then press Enter in this terminal when done.")

        async with async_playwright() as p:
            ctx = await p.chromium.launch_persistent_context(
                user_data_dir=str(profile_path),
                headless=False,
                args=['--no-sandbox', '--disable-dev-shm-usage',
                      '--disable-blink-features=AutomationControlled'],
                viewport={'width': 1280, 'height': 800},
                locale='zh-CN',
            )
            page = ctx.pages[0] if ctx.pages else await ctx.new_page()
            await page.goto(login_url, timeout=60000, wait_until='domcontentloaded')

            await asyncio.get_event_loop().run_in_executor(None, input, "\nPress Enter after login is complete...")

            state = await ctx.storage_state()
            await ctx.close()

        cookies = self._extract_cookies(state)
        if cookies:
            self._save_file(self.get_cookies_path(platform), cookies)
            self._save_storage(self.cookies_dir / f"{platform}_storage.json", state)
            print(f"Saved {len(cookies)} cookies to {self.get_cookies_path(platform)}")
            return True
        else:
            print("No cookies captured.")
            return False

    def force_refresh(self, platform: str) -> Optional[List[Dict]]:
        # 优先从持久化 profile 无扫码刷新（CLI 同步入口，asyncio.run 安全）
        try:
            result = asyncio.run(self.refresh_from_profile(platform))
            if result:
                return result
        except RuntimeError:
            # 已在 event loop 中：调用方应直接 await refresh_from_profile
            pass
        except Exception:
            pass

        # fallback: browser_cookie3（本机多数失效，保留兼容）
        cookies_path = self.get_cookies_path(platform)
        backup = None
        if cookies_path.exists():
            try:
                backup = self._load_file(cookies_path)
            except Exception:
                pass
        result = self._refresh_from_browser(platform)
        if result:
            return result
        if backup:
            self._save_file(cookies_path, backup)
        return None

    def status(self) -> Dict[str, Dict]:
        result = {}
        for platform in PLATFORM_DOMAINS:
            path = self.get_cookies_path(platform)
            if path.exists():
                try:
                    data = json.load(open(path, 'r', encoding='utf-8'))
                    age_hours = (time.time() - path.stat().st_mtime) / 3600
                    result[platform] = {
                        "exists": True,
                        "count": len(data),
                        "age_hours": round(age_hours, 1),
                        "expired": age_hours > _COOKIE_MAX_AGE / 3600,
                    }
                except Exception:
                    result[platform] = {"exists": True, "count": 0, "age_hours": -1, "expired": True}
            else:
                result[platform] = {"exists": False, "count": 0, "age_hours": -1, "expired": True}
        return result


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python -m urlparser.cookies_manager login <platform>")
        print("  python -m urlparser.cookies_manager status")
        print("  python -m urlparser.cookies_manager refresh <platform>")
        print(f"\nSupported platforms: {', '.join(PLATFORM_DOMAINS.keys())}")
        sys.exit(1)

    cmd = sys.argv[1]
    mgr = CookieManager()

    if cmd == "login":
        platform = sys.argv[2] if len(sys.argv) > 2 else "xiaohongshu"
        asyncio.run(mgr.interactive_login(platform))
    elif cmd == "status":
        for p, s in mgr.status().items():
            status_str = "VALID" if s["exists"] and not s["expired"] else "EXPIRED" if s["exists"] else "MISSING"
            print(f"  {p:15s} [{status_str}] {s.get('count', 0)} cookies, age={s.get('age_hours', -1):.1f}h")
    elif cmd == "refresh":
        platform = sys.argv[2] if len(sys.argv) > 2 else "xiaohongshu"
        cookies = mgr.force_refresh(platform)
        if cookies:
            print(f"Refreshed {len(cookies)} cookies for {platform}")
        else:
            print(f"Failed to refresh cookies for {platform}. Try 'login' instead.")
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
