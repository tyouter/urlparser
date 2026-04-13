"""
智能滚动 Mixin
"""

import asyncio
from playwright.async_api import Page


class ScrollingMixin:

    @staticmethod
    async def scroll_to_load_all(
        page: Page,
        max_scrolls: int = 20,
        scroll_delay: float = 1.5,
        max_no_change: int = 5
    ):
        async def get_scroll_height():
            try:
                return await page.evaluate('document.body ? document.body.scrollHeight : 0')
            except Exception:
                return 0

        last_height = await get_scroll_height()
        no_change_count = 0

        for i in range(max_scrolls):
            current_height = await get_scroll_height()

            if current_height == last_height:
                no_change_count += 1
                if no_change_count >= max_no_change:
                    break

            try:
                await page.evaluate('window.scrollTo(0, document.body ? document.body.scrollHeight : 0)')
                await asyncio.sleep(scroll_delay)

                await page.wait_for_load_state('networkidle', timeout=8000)

                new_height = await get_scroll_height()

                if new_height > current_height:
                    no_change_count = 0
                    last_height = new_height
                elif new_height == current_height:
                    no_change_count += 1

            except Exception:
                break

        await page.evaluate('window.scrollTo(0, 0)')

        final_height = await get_scroll_height()
        return final_height