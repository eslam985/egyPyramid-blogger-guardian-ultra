from typing import Optional
import random
import httpx
from playwright.async_api import async_playwright
from downloader_new.shared.logger import get_beast_logger

log = get_beast_logger("lulustream_ext.py")

_USER_AGENTS = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
)

# ── LuluStream ────────────────────────────────────────────────────────────

async def resolve_lulustream(embed_url: str) -> Optional[str]:
    """
    يستخرج رابط التحميل المباشر من LuluStream.
    الخطوات:
      1. يحوّل lulustream.com/e/ → luluvdo.com/d/ للوصول لصفحة التحميل
      2. يضغط زر Download ويجيب روابط الجودات من الـ modal
      3. يختار أعلى جودة (HD)
      4. يعمل POST request مباشرة بـ form data متجاوزاً الـ recaptcha
      5. يستخرج الرابط المباشر من الصفحة الناتجة
    """
    # تحويل embed → download page
    video_id = embed_url.rstrip("/").split("/")[-1]
    target = f"https://luluvdo.com/d/{video_id}"
    log.info(f"🕵️  LuluStream Playwright: {target}")

    ua = random.choice(_USER_AGENTS)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        ctx = await browser.new_context(
            user_agent=ua,
            extra_http_headers={"Referer": "https://lulustream.com/"},
        )
        page = await ctx.new_page()

        try:
            await page.goto(target, wait_until="domcontentloaded", timeout=30_000)

            # ── فحص رابط ميت ──────────────────────────────────────────
            content = await page.content()
            if "no longer available" in content.lower() or "expired" in content.lower() or "deleted" in content.lower():
                log.warning("💀 LuluStream: الفيديو محذوف أو منتهي")
                return "404_DELETED"

            # ── الضغط على زر Download لفتح الـ modal ─────────────────
            log.info("🖱️ LuluStream: فتح modal التحميل...")
            try:
                await page.wait_for_selector(
                    "button[data-bs-target='#modal-download']",
                    state="visible",
                    timeout=40_000,
                )
                await page.click("button[data-bs-target='#modal-download']")
                await page.wait_for_selector(
                    ".modal-body a.btn",
                    state="visible",
                    timeout=40_000,
                )
            except Exception:
                log.warning("⚠️ LuluStream: modal التحميل لم يظهر")
                return None

            # ── سحب أول رابط جودة (HD أو الأعلى) ────────────────────
            quality_href = await page.get_attribute(".modal-body a.btn", "href")
            if not quality_href:
                log.warning("⚠️ LuluStream: مفيش روابط جودة في الـ modal")
                return None

            # الرابط ممكن relative أو absolute
            if quality_href.startswith("/"):
                quality_url = f"https://luluvdo.com{quality_href}"
            elif quality_href.startswith("http"):
                quality_url = quality_href
            else:
                quality_url = f"https://luluvdo.com/{quality_href}"

            log.info(f"🔗 LuluStream: صفحة الجودة: {quality_url}")

            # ── فتح صفحة الجودة وسحب الـ form data ──────────────────
            dl_page = await ctx.new_page()
            await dl_page.goto(quality_url, wait_until="domcontentloaded", timeout=30_000)

            # فحص تاني للـ expired في الصفحة دي
            dl_content = await dl_page.content()
            if "no longer available" in dl_content.lower() or "expired" in dl_content.lower():
                await dl_page.close()
                log.warning("💀 LuluStream: الرابط منتهي الصلاحية")
                return "404_DELETED"

            # سحب الـ form fields
            op    = await dl_page.get_attribute("input[name='op']", "value")
            fid   = await dl_page.get_attribute("input[name='id']", "value")
            mode  = await dl_page.get_attribute("input[name='mode']", "value")
            fhash = await dl_page.get_attribute("input[name='hash']", "value")
            action = await dl_page.evaluate("document.getElementById('F1').action")

            await dl_page.close()

            if not all([op, fid, fhash]):
                log.warning("⚠️ LuluStream: form data ناقص")
                return None

            log.info(f"📋 LuluStream form: op={op} id={fid} mode={mode}")

            # ── POST مباشر بالـ form data متجاوزاً الـ recaptcha ─────
            post_url = action if action else quality_url
            form_data = {
                "op": op,
                "id": fid,
                "mode": mode or "h",
                "hash": fhash,
            }

            headers = {
                "User-Agent": ua,
                "Referer": quality_url,
                "Origin": "https://luluvdo.com",
                "Content-Type": "application/x-www-form-urlencoded",
            }

            log.info("📤 LuluStream: POST request لجلب الرابط المباشر...")
            async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
                resp = await client.post(post_url, data=form_data, headers=headers)

            if resp.status_code not in (200, 302):
                log.warning(f"⚠️ LuluStream POST فشل: HTTP {resp.status_code}")
                return None

            # ── استخراج الرابط المباشر من الـ response ───────────────
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, "html.parser")

            # الرابط المباشر في وسم <a> بعد جدول المعلومات
            direct_a = soup.select_one(".mb-4 ~ a, .the_box a, a[href*='tnmr.org'], a[href*='.mp4']")
            if not direct_a:
                # fallback: أي رابط فيه .mp4
                import re
                mp4_match = re.search(r'https?://[^\s"\']+\.mp4[^\s"\']*', resp.text)
                if mp4_match:
                    direct_url = mp4_match.group(0)
                    log.info(f"✅ LuluStream direct URL (regex): {direct_url[:60]}...")
                    return direct_url
                log.warning("⚠️ LuluStream: مفيش رابط مباشر في الـ response")
                return None

            direct_url = direct_a.get("href", "")
            if not direct_url:
                log.warning("⚠️ LuluStream: الرابط المباشر فاضي")
                return None

            log.info(f"✅ LuluStream direct URL: {direct_url[:60]}...")
            return direct_url

        except Exception as e:
            log.warning(f"❌ LuluStream extraction failed: {e}")
            return None
        finally:
            await browser.close()