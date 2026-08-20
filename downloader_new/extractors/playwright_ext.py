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

            # لو محتاج تحميل → نستخدم page.request من نفس الـ browser session
            if output_path:
                log.info(f"⬇️ بدء التحميل بـ page.request...")
                response = await page.request.get(direct_link, headers={
                    "Referer": "https://down.vidtube.one/",
                    "User-Agent": "Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Mobile Safari/537.36",
                    "Accept": "*/*",
                    "Accept-Encoding": "identity",
                    "Range": "bytes=0-1048576",  # ← طلب أول MB بس للتجربة
                })
                log.info(f"📡 Status: {response.status} | Headers: {dict(response.headers)}")
                if response.ok:
                    body = await response.body()
                    with open(output_path, 'wb') as f:
                        f.write(body)
                    file_size = len(body)
                    log.info(f"✅ حجم الملف: {file_size/1_000_000:.1f} MB")
                    await browser.close()
                    if file_size < 1_000_000:
                        log.error(f"❌ الملف صغير جداً ({file_size} bytes)")
                        os.remove(output_path)
                        return None
                    return output_path
                else:
                    log.error(f"❌ فشل page.request: {response.status}")
                    await browser.close()
                    return None

            else:
                await browser.close()
                return direct_link

        except Exception as e:
            log.error(f"❌ خطأ: {str(e)}")
            await browser.close()
            return None


async def resolve_direct_url(raw_url: str, output_path: str = None) -> str:
    # === TEST مؤقت ===
    if "vidtube.one" in raw_url or "cdn-tube" in raw_url:
        import httpx
            # استخراج الـ ID من أي شكل للرابط
        file_id = raw_url.split("/")[-1].replace(".html", "").split("_")[0] 
        test_url = f"https://down.vidtube.one/d/{file_id}_h"
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                resp = await client.get(test_url, headers={
                    "User-Agent": "Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Mobile Safari/537.36"
                })
                import re
                match = re.search(r'href="(https://serv-stream[^"]+)"', resp.text)
                if match:
                    direct = match.group(1).replace("&amp;", "&")
                    log.info(f"🧪 TEST رابط مباشر: {direct[:80]}")
                    # جرب تحمله
                    async with client.stream("GET", direct, headers={
                        "Referer": "https://down.vidtube.one/",
                        "User-Agent": "Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Mobile Safari/537.36"
                    }) as r:
                        log.info(f"🧪 TEST status: {r.status_code}")
                else:
                    log.info(f"🧪 TEST مش لاقي رابط في الصفحة")
                    log.info(f"🧪 HTML snippet: {resp.text[2000:3500]}")
        except Exception as e:
            log.info(f"🧪 TEST error: {e}")
    # === نهاية TEST ===
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