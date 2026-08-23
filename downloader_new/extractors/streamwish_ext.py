from typing import Optional
import random
import asyncio
from playwright.async_api import async_playwright
from downloader_new.shared.logger import get_beast_logger

log = get_beast_logger("streamwish_ext.py")

_USER_AGENTS = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
)

# ── StreamWish ────────────────────────────────────────────────────────────

async def resolve_streamwish(embed_url: str) -> Optional[str]:
    """
    يستخرج رابط التحميل المباشر من StreamWish.
    الخطوات:
      1. يبني رابط /f/CODE_n مباشرة بدون فتح /d/
      2. يشيل الـ overlay الشفاف بـ JS
      3. يسحب الـ form data ويعمل POST متجاوزاً الـ recaptcha
      4. يستخرج الرابط المباشر من الـ response
    """
    # استخراج الـ CODE من الـ embed URL
    video_id = embed_url.rstrip("/").split("/")[-1]
    # بناء رابط /f/ مباشرة — بدون فتح /d/
    from urllib.parse import urlparse
    parsed = urlparse(embed_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    quality_url = f"{base}/f/{video_id}_n"

    log.info(f"🕵️  StreamWish Playwright: {quality_url}")

    ua = random.choice(_USER_AGENTS)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        ctx = await browser.new_context(
            user_agent=ua,
            extra_http_headers={"Referer": f"{base}/"},
        )
        page = await ctx.new_page()

        try:
            await page.goto(quality_url, wait_until="domcontentloaded", timeout=30_000)

            # ── فحص رابط ميت ──────────────────────────────────────────
            content = await page.content()
            if "file not found" in content.lower() or "no longer available" in content.lower():
                log.warning("💀 StreamWish: الفيديو محذوف")
                return "404_DELETED"

            # ── شيل الـ overlay الشفاف ────────────────────────────────
            await page.evaluate("""
                document.querySelectorAll('div[style*="z-index:2147483647"]').forEach(el => el.remove());
            """)

            # ── انتظار ظهور الـ form ──────────────────────────────────
            try:
                await page.wait_for_selector("#F1", state="attached", timeout=15_000)
            except Exception:
                log.warning("⚠️ StreamWish: form #F1 لم يظهر")
                return None

            # ── إرسال الـ Form مباشرة من داخل المتصفح (للحفاظ على الكوكيز وحماية Cloudflare) ──
            log.info("📤 StreamWish: إرسال النموذج من داخل المتصفح...")
            await page.evaluate("document.getElementById('F1').submit()")
            await page.wait_for_load_state("domcontentloaded", timeout=30_000)

            # ── استخراج الرابط المباشر من الصفحة الناتجة ──────────────
            try:
                await page.wait_for_selector(".text-center a[href*='.mp4'], .text-center a.btn", timeout=10_000)
                direct_url = await page.get_attribute(".text-center a[href*='.mp4'], .text-center a.btn", "href")
                if direct_url:
                    log.info(f"✅ StreamWish direct URL: {direct_url[:60]}...")
                    return direct_url
            except Exception:
                pass

            # fallback: regex من محتوى الصفحة
            page_text = await page.content()
            import re
            mp4_match = re.search(r'https?://[^\s"\']+\.mp4[^\s"\']*', page_text)
            if mp4_match:
                direct_url = mp4_match.group(0)
                log.info(f"✅ StreamWish direct URL (regex): {direct_url[:60]}...")
                return direct_url

            log.warning("⚠️ StreamWish: مفيش رابط مباشر في الـ response")
            return None

        except Exception as e:
            log.warning(f"❌ StreamWish extraction failed: {e}")
            return None
        finally:
            await browser.close()