import logging
import time
from typing import Any

from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

_PAGE_STATE_JS = """\
(() => {
  function isVisible(el) {
    var style = window.getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden') return false;
    if (el.getAttribute('aria-hidden') === 'true') return false;
    if (parseFloat(style.opacity) === 0) return false;
    var rect = el.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  }

  function getText(el) {
    var ariaLabel = el.getAttribute('aria-label');
    if (ariaLabel && ariaLabel.trim()) return ariaLabel.trim().substring(0, 100);

    var labelledBy = el.getAttribute('aria-labelledby');
    if (labelledBy) {
      var labelEl = document.getElementById(labelledBy);
      if (labelEl && labelEl.innerText.trim()) return labelEl.innerText.trim().substring(0, 100);
    }

    var parentLabel = el.closest('label');
    if (parentLabel && parentLabel.innerText.trim()) {
      return parentLabel.innerText.replace(/\\s+/g, ' ').trim().substring(0, 100);
    }

    if (el.id) {
      var forLabel = document.querySelector('label[for="' + CSS.escape(el.id) + '"]');
      if (forLabel && forLabel.innerText.trim()) {
        return forLabel.innerText.replace(/\\s+/g, ' ').trim().substring(0, 100);
      }
    }

    var placeholder = el.getAttribute('placeholder');
    if (placeholder && placeholder.trim()) return placeholder.trim().substring(0, 100);

    var name = el.getAttribute('name');
    if (name && name.trim()) return name.trim().substring(0, 100);

    var title = el.getAttribute('title');
    if (title && title.trim()) return title.trim().substring(0, 100);

    var text = el.innerText;
    if (text && text.trim()) {
      return text.replace(/\\s+/g, ' ').trim().substring(0, 100);
    }

    return '';
  }

  function getSelector(el) {
    if (el.id && !/^\\d/.test(el.id)) return '#' + CSS.escape(el.id);

    var testid = el.getAttribute('data-testid');
    if (testid) return '[data-testid="' + testid + '"]';

    var nm = el.getAttribute('name');
    if (nm) return '[name="' + nm + '"]';

    var al = el.getAttribute('aria-label');
    if (al) return '[aria-label="' + CSS.escape(al) + '"]';

    return null;
  }

  function getRole(el) {
    var role = el.getAttribute('role');
    if (role) return role;

    var tag = el.tagName.toLowerCase();
    if (tag === 'a' && el.hasAttribute('href')) return 'link';
    if (tag === 'button') return 'button';
    if (tag === 'input') {
      var t = (el.getAttribute('type') || 'text').toLowerCase();
      if (t === 'submit' || t === 'button' || t === 'image' || t === 'reset') return 'button';
      if (t === 'checkbox') return 'checkbox';
      if (t === 'radio') return 'radio';
      return 'textbox';
    }
    if (tag === 'select') return 'combobox';
    if (tag === 'textarea') return 'textbox';
    if (tag === 'summary') return 'button';
    return tag;
  }

  var interactiveElements = [];
  var query = 'button, a[href], input:not([type="hidden"]), select, textarea, ';
  query += '[role="button"], [role="link"], [role="textbox"], [role="combobox"], ';
  query += '[role="checkbox"], [role="radio"], summary, [onclick]';

  var els = document.querySelectorAll(query);
  for (var i = 0; i < els.length; i++) {
    var el = els[i];
    if (!isVisible(el)) continue;
    var text = getText(el);
    if (!text && el.tagName.toLowerCase() === 'div') continue;
    interactiveElements.push({
      tag: el.tagName.toLowerCase(),
      text: text,
      role: getRole(el),
      selector: getSelector(el)
    });
    if (interactiveElements.length >= 60) break;
  }

  var headings = [];
  var headingEls = document.querySelectorAll('h1,h2,h3,h4,h5,h6');
  for (var i = 0; i < headingEls.length; i++) {
    var h = headingEls[i];
    if (!isVisible(h)) continue;
    var text = h.innerText.replace(/\\s+/g, ' ').trim();
    if (text) headings.push({tag: h.tagName.toLowerCase(), text: text.substring(0, 200)});
  }

  var body = document.body;
  var visibleText = body ? body.innerText.replace(/\\s+/g, ' ').trim().substring(0, 500) : '';

  return {
    interactive_elements: interactiveElements,
    headings: headings,
    visible_text: visibleText
  };
})()\
"""


class BrowserManager:
    def __init__(self):
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None

    async def start(self):
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=False, args=["--disable-blink-features=AutomationControlled"]
        )
        self._context = await self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="en-US",
            timezone_id="America/Los_Angeles",
        )
        self._page = await self._context.new_page()
        await self._context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined })"
        )

    async def execute(self, action: dict[str, Any]) -> dict[str, Any]:
        type_ = action["type"]
        start = time.monotonic()
        status = "success"
        error = None
        screenshot_path = None
        try:
            if type_ == "goto":
                await self._page.goto(action["url"], wait_until="load")
            elif type_ == "click":
                await self._page.click(action["target"])
            elif type_ == "type":
                # await self._page.triple_click(action["target"])
                for i in range(3):
                    await self._page.click(action["target"])
                await self._page.type(action["target"], action["text"], delay=80)
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
            logger.debug("get_page_state: page not initialized")
            return {}
        for attempt in range(2):
            try:
                dom = await self._page.evaluate(_PAGE_STATE_JS)
                elements = dom.get("interactive_elements", [])
                headings = dom.get("headings", [])
                visible_text = dom.get("visible_text", "")
                logger.debug(
                    "Page state: url=%s title=%s elements=%d headings=%d visible_text_len=%d",
                    self._page.url,
                    await self._page.title(),
                    len(elements),
                    len(headings),
                    len(visible_text),
                )
                return {
                    "url": self._page.url,
                    "title": await self._page.title(),
                    "interactive_elements": elements,
                    "headings": headings,
                    "visible_text": visible_text,
                }
            except Exception as e:
                if "Execution context was destroyed" in str(e) and attempt == 0:
                    await self._page.wait_for_load_state("domcontentloaded")
                    continue
                logger.warning("Failed to extract smart DOM", exc_info=True)
                return {
                    "url": self._page.url,
                    "title": await self._page.title(),
                    "interactive_elements": [],
                    "headings": [],
                    "visible_text": "",
                }
        return {}

    async def get_screenshot_bytes(self) -> bytes | None:
        if self._page is None:
            return None
        try:
            return await self._page.screenshot(type="png")
        except Exception:
            return None

    async def stop(self):
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
