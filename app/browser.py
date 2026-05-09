import logging
import time
from typing import Any

from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)


class BrowserManager:
    def __init__(self):
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None

    async def start(self):
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=True)
        self._context = await self._browser.new_context()
        self._page = await self._context.new_page()

    async def execute(self, action: dict[str, Any]) -> dict[str, Any]:
        type_ = action["type"]
        start = time.monotonic()
        status = "success"
        error = None
        screenshot_path = None
        try:
            if type_ == "goto":
                await self._page.goto(action["url"], wait_until="domcontentloaded")
            elif type_ == "click":
                await self._page.click(action["target"])
            elif type_ == "type":
                await self._page.fill(action["target"], action["text"])
            elif type_ == "press":
                await self._page.keyboard.press(action["key"])
            elif type_ == "scroll":
                await self._page.evaluate(
                    f"window.scrollBy(0, {action.get('amount', 300)})"
                )
            elif type_ == "screenshot":
                path = f"artifacts/screenshots/{action.get('name', 'step')}.png"
                await self._page.screenshot(path=path)
                screenshot_path = path
            else:
                status = "failed"
                error = f"Unknown action type: {type_}"
        except Exception as e:
            status = "failed"
            error = str(e)
        latency_ms = round((time.monotonic() - start) * 1000, 2)
        return {
            "action_type": type_,
            "action_data": action,
            "status": status,
            "error": error,
            "latency_ms": latency_ms,
            "screenshot_path": screenshot_path,
        }

    async def get_page_state(self) -> dict[str, Any]:
        if self._page is None:
            return {}
        return {
            "url": self._page.url,
            "title": await self._page.title(),
        }

    async def stop(self):
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
