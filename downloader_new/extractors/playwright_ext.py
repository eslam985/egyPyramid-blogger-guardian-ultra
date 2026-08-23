# /media/es/DDrive/projects/apps-python/egyPyramid-guardian-ultra/downloader_new/extractors/playwright_ext.py
import os
from playwright.async_api import async_playwright
import asyncio
from downloader_new.shared.logger import get_beast_logger
from downloader_new.extractors.mixdrop_ext import get_mixdrop_direct_link
from downloader_new.extractors.extract_streamtape import resolve_streamtape
from downloader_new.extractors.doodstream_ext import resolve_doodstream
from downloader_new.extractors.lulustream_ext import resolve_lulustream
from downloader_new.extractors.streamwish_ext import resolve_streamwish
log = get_beast_logger("playwright_ext:")

async def get_direct_link_via_playwright(embed_url, output_path=None):
    file_id = embed_url.split("embed-")[-1].replace(".html", "")
    quality_page_url = f"https://down.vidtube.one/d/{file_id}"

    log.info(f"🔍 الخطوة 1: صفحة اختيار الجودة: {quality_page_url}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled", "--disable-dev-shm-usage"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Mobile Safari/537.36",
            viewport={"width": 1280, "height": 720},
            java_script_enabled=True,
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            }
        )
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        """)
        page = await context.new_page()
        await page.add_init_script("window.chrome = { runtime: {} };")

        try:
            await page.goto(quality_page_url, wait_until="networkidle", timeout=45000)
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

            btn_selector = "a.btn-gradient.submit-btn"
            await page.wait_for_selector(btn_selector, state="visible", timeout=20000)

            direct_link = await page.get_attribute(btn_selector, "href")

            if not direct_link or "http" not in direct_link:
                log.error("❌ الرابط المستخرج غير صالح.")
                await browser.close()
                return None

            log.info(f"✅ تم صيد الرابط: {direct_link[:60]}...")

            # لم نعد نستخدم المتصفح الوهمي للتحميل الفعلي. نرجع الرابط المباشر فقط.
            await browser.close()
            return direct_link

        except Exception as e:
            log.error(f"❌ خطأ في Playwright: {str(e)}")
            await browser.close()
            return None


async def resolve_direct_url(raw_url: str, output_path: str = None) -> str:
    """يستخرج الرابط المباشر من رابط embed واحد فقط. يرمي Exception لو فشل."""

    if "vidtube.one" in raw_url or "cdn-tube" in raw_url:
        log.info("🎯 VidTube.. جاري الصيد...")
        try:
            # تم حذف تمرير output_path لضمان عدم حدوث تحميل بداخل Playwright
            result = await asyncio.wait_for(
                get_direct_link_via_playwright(raw_url),
                timeout=3600
            )
            if result:
                return result
            raise RuntimeError("فشل صيد VidTube")
        except asyncio.TimeoutError:
            raise RuntimeError("Timeout: VidTube")

    elif "mixdrop" in raw_url:
        log.info("🎯 MixDrop.. جاري الصيد...")
        try:
            direct_link = await asyncio.wait_for(get_mixdrop_direct_link(raw_url), timeout=240)
            if direct_link == "404_DELETED":
                raise RuntimeError("💀 MixDrop: الملف محذوف")
            if direct_link:
                return direct_link
            raise RuntimeError("فشل صيد MixDrop")
        except asyncio.TimeoutError:
            raise RuntimeError("Timeout: MixDrop")

    elif "streamtape" in raw_url or "stape" in raw_url or "shstream" in raw_url:
        log.info("🎯 Streamtape.. جاري الصيد...")
        try:
            direct_link = await asyncio.wait_for(resolve_streamtape(raw_url), timeout=120)
            if direct_link == "404_DELETED":
                raise RuntimeError("💀 Streamtape: الملف محذوف")
            if direct_link:
                return direct_link
            raise RuntimeError("فشل صيد Streamtape")
        except asyncio.TimeoutError:
            raise RuntimeError("Timeout: Streamtape")

    elif "doodstream" in raw_url or "playmogo" in raw_url or "d0o0d" in raw_url:
        log.info("🎯 Doodstream.. جاري الصيد...")
        try:
            direct_link = await asyncio.wait_for(resolve_doodstream(raw_url), timeout=120)
            if direct_link == "404_DELETED":
                raise RuntimeError("💀 Doodstream: الملف محذوف")
            if direct_link:
                return direct_link
            raise RuntimeError("فشل صيد Doodstream")
        except asyncio.TimeoutError:
            raise RuntimeError("Timeout: Doodstream")

    elif "lulustream" in raw_url or "luluvdo" in raw_url:
        log.warning("⏭️ تخطي LuluStream مؤقتاً بناءً على الطلب (زر التحميل غير ظاهر).")
        raise RuntimeError("تخطي LuluStream مؤقتاً")
        
    elif "streamwish" in raw_url:
        direct_link = await asyncio.wait_for(resolve_streamwish(raw_url), timeout=120)
        if direct_link == "404_DELETED":
            raise RuntimeError("💀 StreamWish: الملف محذوف")
        if direct_link:
            return direct_link
        raise RuntimeError("فشل صيد StreamWish")
    # رابط مباشر مش محتاج استخراج
    return raw_url