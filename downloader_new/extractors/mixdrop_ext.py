# /media/es/DDrive/projects/apps-python/egyPyramid-guardian-ultra/downloader_new/extractors/mixdrop_ext.py
import random

from playwright.async_api import async_playwright
# الاستدعاء النظيف والمباشر للوجر
from downloader_new.shared.logger import get_beast_logger
from downloader_new.shared.logger import get_beast_logger
log = get_beast_logger("GuardianUltra")

# قائمة الوكلاء
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
]
async def get_mixdrop_direct_link(embed_url):
    target_url = embed_url.replace("/e/", "/f/")
    if "?download" not in target_url:
        target_url += "?download"

    log.info(f"🕵️ محاكاة سلوك بشري على: {target_url}")

    async with async_playwright() as p:
        # إضافة args للتمويه وتجاوز حماية الـ Bot Detection
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--window-size=1920,1080"
            ]
        )
        context = await browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport={"width": 1920, "height": 1080}
        )
        page = await context.new_page()

        try:
            # --- 🚀 التنصت الآمن: صيد الروابط من الشبكة مباشرة 🚀 ---
            captured_direct_url = None
            
            async def handle_response(response):
                nonlocal captured_direct_url
                # نتأكد أن الرابط هو رابط محتوى فيديو وليس مجرد صفحة إعلانات
                if any(domain in response.url for domain in ["mxcontent", "mdelivery", "mxdcontent"]):
                    captured_direct_url = response.url

            page.on("response", handle_response)
            # -------------------------------------------------------------

            await page.goto(target_url, wait_until="domcontentloaded")

            # --- 🔍 فحص هل الملف محذوف فعلياً من المصدر ---
            page_content = await page.content()
            if "can't find the file you are looking for" in page_content:
                log.error("🚫 الرابط ميت: MixDrop بيقول We can't find the file")
                await browser.close()
                return "404_DELETED"

            btn_selector = "a.download-btn"

            # رفعنا المدى لـ 10 لضمان وجود محاولات كافية بعد الـ Reload
            for i in range(1, 11):
                try:
                    await page.wait_for_selector(
                        btn_selector, state="visible", timeout=10000
                    )
                    log.info(f"🖱️ نقرة رقم {i}...")

                    # --- ⚡ تعديل الـ Reload الذكي ⚡ ---
                    if i == 5:
                        log.info(
                            "🔄 الموقع يبدو متجمداً.. جاري إعادة تحميل الصفحة (Reload) للتنشيط..."
                        )
                        await page.reload(wait_until="domcontentloaded")
                        await page.wait_for_timeout(3000)
                        continue
                    # ----------------------------------
                    try:
                        async with context.expect_page(timeout=10000) as new_page_info:
                            await page.click(btn_selector)

                        ad_page = await new_page_info.value
                        log.info(f"📺 إعلان ظهر، ننتظره قليلاً...")
                        await page.wait_for_timeout(5000)
                        await ad_page.close()
                    except Exception:
                        log.warning(f"⚠️ النقرة {i} لم تفتح إعلاناً.")
                    # ----------------------------------

                    await page.bring_to_front()

                    # --- 1. فحص هل تم صيد الرابط السري من الشبكة (AJAX POST) ---
                    if captured_direct_url:
                        log.info(f"✅ تم صيد الرابط السري من الشبكة بنجاح: {captured_direct_url[:60]}...")
                        await browser.close()
                        return captured_direct_url

                    # --- 2. فحص الرابط المباشر بالطريقة الكلاسيكية (من الـ href) ---
                    href = await page.get_attribute(btn_selector, "href")

                    if href and href.startswith("http"):
                        # تصحيح الثغرة: إضافة الدومينات الوهمية الجديدة لمنع التقييم الخاطئ
                        valid_domains = ["mxcontent", "mdelivery", "mxdcontent", "delivery"]
                        invalid_terms = ["?download", "mixdrop", "miixdrop", "mixdrop.ps"]
                        
                        is_valid_direct = any(domain in href.lower() for domain in valid_domains) or not any(term in href.lower() for term in invalid_terms)

                        if is_valid_direct:
                            log.info(f"✅ تم صيد الرابط بنجاح من الزر: {href[:60]}...")
                            await browser.close()
                            return href

                    log.info("⏳ الرابط لم يظهر بعد، ننتظر ثواني للنقرة التالية...")
                    await page.wait_for_timeout(
                        5000
                    )  # زودنا الانتظار لـ 5 ثواني عشان ندي فرصة للسيرفر
                except Exception as e:
                    log.warning(f"⚠️ خطأ في المحاولة {i}: {str(e)}")
                    continue  # لو محاولة فشلت يكمل للي بعدها ميفصلش السكريبت

            await browser.close()
            return None

        except Exception as e:
            try:
                page_content = await page.content()
                log.error(f"🔍 [DEBUG] محتوى الصفحة عند الفشل (أول 500 حرف): {page_content[:500]}")
            except:
                pass
            log.error(f"❌ خطأ أثناء المحاكاة البشرية: {str(e)}")
            await browser.close()
            return None

