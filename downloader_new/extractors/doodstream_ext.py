from typing import Optional
import random
from playwright.async_api import async_playwright
from downloader_new.shared.logger import get_beast_logger

log = get_beast_logger("doodstream_ext.py")

_USER_AGENTS = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
)

# ── Doodstream ────────────────────────────────────────────────────────────

async def resolve_doodstream(embed_url: str) -> Optional[str]:
    """
    يستخرج رابط التحميل المباشر من Doodstream/playmogo.
    الخطوات:
      1. يحوّل /e/ → /d/ للوصول لصفحة التحميل
      2. ينتظر ظهور .download-content (بعد عداد 5 ثواني)
      3. يضغط على رابط Original ويجيب صفحة التحميل النهائية
      4. يستخرج الرابط المباشر من .the_box
    """
    # تحويل embed → download page
    target = embed_url.replace("/e/", "/d/")
    log.info(f"🕵️  Doodstream Playwright: {target}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        ctx = await browser.new_context(user_agent=random.choice(_USER_AGENTS))
        page = await ctx.new_page()

        try:
            await page.goto(target, wait_until="domcontentloaded", timeout=30_000)

            # ── فحص رابط ميت ──────────────────────────────────────────
            content = await page.content()
            if "video you are looking for is not found" in content.lower():
                log.warning("💀 Doodstream: الفيديو محذوف")
                return "404_DELETED"

            # ── انتظار ظهور .download-content بعد العداد ─────────────
            # الموقع ممكن يغير مدة العداد، فبننتظر فعلياً حتى 30 ثانية
            log.info("⏳ Doodstream: انتظار انتهاء العداد وظهور زر التحميل...")
            try:
                await page.wait_for_selector(
                    ".download-content a.btn",
                    state="visible",
                    timeout=30_000,
                )
            except Exception:
                log.warning("⚠️ Doodstream: زر التحميل لم يظهر بعد العداد")
                return None

            # ── سحب رابط صفحة Original ────────────────────────────────
            download_page_href = await page.get_attribute(".download-content a.btn", "href")
            if not download_page_href:
                log.warning("⚠️ Doodstream: مفيش href في زر Original")
                return None

            # الرابط ممكن يكون relative
            if download_page_href.startswith("/"):
                from urllib.parse import urlparse
                parsed = urlparse(target)
                download_page_url = f"{parsed.scheme}://{parsed.netloc}{download_page_href}"
            else:
                download_page_url = download_page_href

            log.info(f"🔗 Doodstream: صفحة التحميل النهائية: {download_page_url}")

            # ── فتح صفحة التحميل النهائية وسحب الرابط المباشر ─────────
            dl_page = await ctx.new_page()
            await dl_page.goto(download_page_url, wait_until="domcontentloaded", timeout=30_000)

            # الرابط المباشر في .the_box a
            direct_href = await dl_page.get_attribute(".the_box a", "href")
            await dl_page.close()

            if not direct_href:
                log.warning("⚠️ Doodstream: مفيش رابط مباشر في .the_box")
                return None

            log.info(f"✅ Doodstream direct URL: {direct_href[:60]}...")
            return direct_href

        except Exception as e:
            log.warning(f"❌ Doodstream extraction failed: {e}")
            return None
        finally:
            await browser.close()