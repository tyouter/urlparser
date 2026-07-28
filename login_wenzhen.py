"""问真八字登录 — 持久化 profile 版本
启动后浏览器打开问真首页，手动登录，然后在聊天说'登了'触发保存。
持久化 profile 保留完整登录态，后续 WenzhenParser 自动加载。
"""
import asyncio, os, shutil
from pathlib import Path
from playwright.async_api import async_playwright

SIGNAL = Path("D:/Hermes/projects/urlparser/tmp/login_done.signal")
PROFILE = Path.home() / ".urlparser" / "profiles" / "wenzhen"

async def main():
    # 清理旧 profile（如果存在且损坏）
    if PROFILE.exists():
        shutil.rmtree(PROFILE)
    PROFILE.mkdir(parents=True, exist_ok=True)

    # 清理旧信号
    if SIGNAL.exists():
        SIGNAL.unlink()

    async with async_playwright() as p:
        print(f"启动浏览器 (profile: {PROFILE})...")
        ctx = await p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE),
            headless=False,
            args=['--no-sandbox', '--disable-dev-shm-usage',
                  '--disable-blink-features=AutomationControlled'],
            viewport={'width': 1280, 'height': 800},
            locale='zh-CN',
        )
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        await page.goto("https://pcbz.iwzwh.com", timeout=60000, wait_until="domcontentloaded")
        
        print("浏览器已打开。去登录，完成后在聊天里说'登了'。")
        print(f"等待信号: {SIGNAL}")
        
        while not SIGNAL.exists():
            await asyncio.sleep(2)
        
        print("收到信号，正在保存...")
        await ctx.close()
        print(f"登录态已保存到: {PROFILE}")
        print("完成！可以关闭终端了。")

if __name__ == "__main__":
    asyncio.run(main())
