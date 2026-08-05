from typing import Optional
import random
from playwright.async_api import async_playwright
from downloader_new.shared.log import get_beast_logger

log = get_beast_logger("extract_streamtape.py")

_USER_AGENTS = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
)
# ── Streamtape ────────────────────────────────────────────────────────────

async def resolve_streamtape(embed_url: str) -> Optional[str]:
    # تحويل الرابط إلى صيغة صفحة التحميل /v/ بدلاً من الـ Embed /e/
    target = embed_url.replace("/e/", "/v/").replace("/f/", "/v/")
    log.info(f"🕵️  Streamtape Playwright: {target}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        ctx = await browser.new_context(user_agent=random.choice(_USER_AGENTS))
        page = await ctx.new_page()

        try:
            await page.goto(target, wait_until="domcontentloaded")

            # 1. محاولة قنص الرابط مباشرة من العنصر المخفي لتفادي الكابتشا وتأخير الضغط
            try:
                raw_link = await page.locator("#norobotlink").text_content(timeout=5000)
                if raw_link and "get_video" in raw_link:
                    raw_link = raw_link.strip()
                    if raw_link.startswith("//"):
                        raw_link = f"https:{raw_link}"
                    final_url = raw_link if "dl=1" in raw_link else f"{raw_link}&dl=1"
                    log.info(f"✅ Streamtape URL extracted directly from DOM: {final_url[:60]}...")
                    return final_url
            except Exception:
                log.debug("Streamtape: Direct DOM extraction failed, falling back to click method...")

            # 2. الطريقة الاحتياطية (في حال عدم وجود الرابط في الـ DOM مباشرة)
            btn = "#downloadvideo"
            await page.wait_for_selector(btn, state="visible", timeout=15_000)

            # 1. الضغط على الزر مرة واحدة لتشغيل العداد الزمني (Counter) الخاص بالموقع
            try:
                async with ctx.expect_page(timeout=5000) as new_page_info:
                    await page.click(btn)
                # إغلاق نافذة الإنبثاق (Popup) الناتجة عن الضغطة الأولى إذا ظهرت
                ad_page = await new_page_info.value
                await ad_page.close()
            except Exception:
                pass

            await page.bring_to_front()

            # 2. الانتظار لمدة 6 ثوانٍ حتى ينتهي العداد (5 ثوانٍ) ويقوم السكربت بحقن الرابط
            log.info("⏳ Streamtape: Waiting for 5s countdown to finish...")
            await page.wait_for_timeout(6000)

            # 3. استخراج الرابط النهائي من الخاصية href للزر
            href = await page.get_attribute(btn, "href")

            if href and "get_video" in href:
                href = href.strip()
                final_url = f"https:{href}" if href.startswith("//") else href
                log.info(f"✅ Streamtape direct URL resolved: {final_url[:60]}...")
                return final_url

            # فحص محتوى الصفحة لمعرفة سبب الفشل بدقة
            page_text = await page.inner_text("body")
            is_dead = "video no longer available" in page_text.lower() or "not found" in page_text.lower()
            
            log.warning(f"❌ Streamtape failed. Actual href: '{href}' | Is File Deleted: {is_dead}")
            return None

        except Exception as e:
            log.warning(f"❌ Streamtape extraction failed: {e}")
            return None
        finally:
            await browser.close()