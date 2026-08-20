# /media/es/DDrive/projects/apps-python/egyPyramid-guardian-ultra/downloader_new/extractors/playwright_ext.py
from playwright.async_api import async_playwright
import asyncio
# الاستدعاء النظيف والمباشر للوجر
from downloader_new.shared.logger import get_beast_logger
from downloader_new.extractors.mixdrop_ext import get_mixdrop_direct_link
from downloader_new.extractors.extract_streamtape import resolve_streamtape

log = get_beast_logger("GuardianUltra")

async def get_direct_link_via_playwright(embed_url):
    file_id = embed_url.split("embed-")[-1].replace(".html", "")
    quality_page_url = f"https://down.vidtube.one/d/{file_id}"

    log.info(f"🔍 الخطوة 1: صفحة اختيار الجودة: {quality_page_url}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720},
            java_script_enabled=True,
            # إخفاء علامات الأتمتة
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            }
        )
        
        # إخفاء webdriver flag
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        """)
        
        page = await context.new_page()
        await page.add_init_script("window.chrome = { runtime: {} };")
        try:
            await page.goto(quality_page_url, wait_until="networkidle", timeout=45000)
            # ننتظر شوية بعد التحميل
            await page.wait_for_timeout(3000)

            quality_selector = "a.btn.btn-light"
            await page.wait_for_selector(quality_selector, state="visible", timeout=15000)
            quality_links = await page.query_selector_all(quality_selector)

            if not quality_links:
                log.error("❌ لم يتم العثور على روابط الجودة.")
                await browser.close()
                return None

            best_quality_href = await quality_links[0].get_attribute("href")
            log.info(f"🎯 أعلى جودة متاحة: {best_quality_href}")

            if best_quality_href.startswith("/"):
                download_page_url = f"https://down.vidtube.one{best_quality_href}"
            else:
                download_page_url = best_quality_href

            log.info(f"🔍 الخطوة 2: صفحة التحميل: {download_page_url}")
            await page.goto(download_page_url, wait_until="networkidle", timeout=45000)
            await page.wait_for_timeout(2000)

            # DEBUG مؤقت
            html = await page.content()
            log.info(f"📄 HTML snippet:\n{html[2000:4000]}")

            btn_selector = "a.btn-gradient.submit-btn"
            log.info("⏳ ننتظر ظهور زر التحميل المباشر...")
            await page.wait_for_selector(btn_selector, state="visible", timeout=20000)

            direct_link = await page.get_attribute(btn_selector, "href")
            await browser.close()

            if direct_link and "http" in direct_link:
                log.info(f"✅ تم صيد الكنز بنجاح: {direct_link[:60]}...")
                return direct_link
            else:
                log.error("❌ الرابط المستخرج غير صالح.")
                return None

        except Exception as e:
            log.error(f"❌ خطأ أثناء الصيد بالمتصفح: {str(e)}")
            await browser.close()
            return None


async def resolve_direct_url(raw_url: str) -> str:
    """
    معالجة روابط vidtube/lulu/mixdrop واستخراج الرابط المباشر.
    """
    # 1. معالجة روابط VidTube/Lulu
    if "vidtube.one" in raw_url or "cdn-tube" in raw_url:
        log.info("🎯 تم اكتشاف رابط VidTube/Lulu.. جاري استخراج الرابط المباشر...")
        try:
            # حماية لمنع السكربت من التعليق (Hang)
            direct_link = await asyncio.wait_for(get_direct_link_via_playwright(raw_url), timeout=240)
            if direct_link:
                log.info(f"✅ تم صيد الرابط بنجاح!")
                raw_url = direct_link
            else:
                log.warning("⚠️ فشل الصيد، سنحاول بالرابط الأصلي.")
        except asyncio.TimeoutError:
            log.error("⏳ تجاوز الوقت: Playwright توقف عن الاستجابة.")

    # 2. معالجة روابط MixDrop
    elif "mixdrop" in raw_url:
        log.info("🎯 تم اكتشاف رابط MixDrop.. جاري الصيد...")
        try:
            # حماية لمنع السكربت من التعليق
            direct_link = await asyncio.wait_for(get_mixdrop_direct_link(raw_url), timeout=240)
            
            if direct_link == "404_DELETED":
                raise Exception("الملف محذوف نهائياً من المصدر (MixDrop 404)")
            
            if direct_link:
                log.info(f"✅ تم صيد رابط MixDrop المباشر بنجاح.")
                raw_url = direct_link
            else:
                log.warning("⚠️ فشل الصيد، سنحاول بالرابط الأصلي.")
        except asyncio.TimeoutError:
            log.error("⏳ تجاوز الوقت: MixDrop توقف عن الاستجابة.")
            raise Exception("Timeout: السكربت عالق في صفحة التحميل.")

    # 3. معالجة روابط Streamtape
    elif "streamtape" in raw_url or "stape" in raw_url or "shstream" in raw_url:
        log.info("🎯 تم اكتشاف رابط Streamtape.. جاري الصيد...")
        try:
            direct_link = await asyncio.wait_for(resolve_streamtape(raw_url), timeout=120)
            if direct_link:
                log.info("✅ تم صيد رابط Streamtape المباشر بنجاح.")
                raw_url = direct_link
            else:
                log.warning("⚠️ فشل الصيد من Streamtape، سنحاول بالرابط الأصلي.")
        except asyncio.TimeoutError:
            log.error("⏳ تجاوز الوقت: Streamtape توقف عن الاستجابة.")
            
    return raw_url