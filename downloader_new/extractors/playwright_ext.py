# /media/es/DDrive/projects/apps-python/egyPyramid-guardian-ultra/downloader_new/extractors/playwright_ext.py
import os
from playwright.async_api import async_playwright
import asyncio
from downloader_new.shared.logger import get_beast_logger
from downloader_new.extractors.mixdrop_ext import get_mixdrop_direct_link
from downloader_new.extractors.extract_streamtape import resolve_streamtape

log = get_beast_logger("GuardianUltra")

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

            # لو محتاج تحميل → نجيب الـ cookies ونحمل بـ httpx
            if output_path:
                cookies = await context.cookies()
                await browser.close()

                cookies_dict = {c['name']: c['value'] for c in cookies}
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    "Referer": "https://down.vidtube.one/",
                    "Origin": "https://down.vidtube.one",
                    "Accept": "video/webp,video/apng,video/*,*/*;q=0.8",
                }

                import httpx
                log.info(f"⬇️ بدء التحميل بـ httpx مع cookies...")
                async with httpx.AsyncClient(cookies=cookies_dict, follow_redirects=True, timeout=3600) as client:
                    async with client.stream("GET", direct_link, headers=headers) as response:
                        log.info(f"📡 HTTP Status: {response.status_code}")
                        if response.status_code != 200:
                            log.error(f"❌ فشل httpx: {response.status_code}")
                            return None

                        total = int(response.headers.get('content-length', 0))
                        downloaded = 0
                        last_log = 0

                        with open(output_path, 'wb') as f:
                            async for chunk in response.aiter_bytes(1024 * 1024):
                                f.write(chunk)
                                downloaded += len(chunk)
                                if total:
                                    pct = downloaded / total * 100
                                    if int(pct) >= last_log + 10:
                                        last_log = int(pct) // 10 * 10
                                        log.info(f"📥 {int(pct)}% | {downloaded/1_000_000:.0f}/{total/1_000_000:.0f} MB")

                file_size = os.path.getsize(output_path)
                if file_size < 1_000_000:
                    log.error(f"❌ الملف صغير جداً ({file_size} bytes)")
                    os.remove(output_path)
                    return None

                log.info(f"✅ اكتمل التحميل: {file_size/1_000_000:.1f} MB")
                return output_path

            else:
                await browser.close()
                return direct_link

        except Exception as e:
            log.error(f"❌ خطأ: {str(e)}")
            await browser.close()
            return None


async def resolve_direct_url(raw_url: str, output_path: str = None) -> str:
    if "vidtube.one" in raw_url or "cdn-tube" in raw_url:
        log.info("🎯 تم اكتشاف رابط VidTube/Lulu.. جاري استخراج الرابط المباشر...")
        try:
            result = await asyncio.wait_for(
                get_direct_link_via_playwright(raw_url, output_path=output_path),
                timeout=3600
            )
            if result:
                log.info(f"✅ تم صيد الرابط بنجاح!")
                # لو output_path موجود → result هو مسار الملف مش رابط
                if output_path:
                    return result  # مسار الملف
                raw_url = result
            else:
                log.warning("⚠️ فشل الصيد، سنحاول بالرابط الأصلي.")
        except asyncio.TimeoutError:
            log.error("⏳ تجاوز الوقت: Playwright توقف عن الاستجابة.")

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