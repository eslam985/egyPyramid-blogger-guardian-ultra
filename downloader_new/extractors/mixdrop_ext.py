# /media/es/DDrive/projects/apps-python/egyPyramid-guardian-ultra/downloader_new/extractors/mixdrop_ext.py
from playwright.async_api import async_playwright
# الاستدعاء النظيف والمباشر للوجر
from downloader_new.shared.logger import get_beast_logger

log = get_beast_logger("GuardianUltra")


async def get_mixdrop_direct_link(embed_url):
    target_url = embed_url.replace("/e/", "/f/")
    if "?download" not in target_url:
        target_url += "?download"

    log.info(f"🕵️ محاكاة سلوك بشري على: {target_url}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True
        )  # يمكن جعلها False لو بتجرب محلياً
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        try:
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

                    # فحص الرابط المباشر - صيد الدومينات الفرعية الجديدة
                    href = await page.get_attribute(btn_selector, "href")

                    if href and href.startswith("http"):
                        # فحص ذكي: هل الرابط يحتوي على كلمة mxcontent (بأي شكل) أو ليس له علاقة بـ mixdrop؟
                        is_valid_direct = "mxcontent" in href or (
                            not ("?download" in href or "mixdrop" in href)
                        )

                        if is_valid_direct:
                            log.info(f"✅ تم صيد الرابط بنجاح: {href[:60]}...")

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
            log.error(f"❌ خطأ أثناء المحاكاة البشرية: {str(e)}")
            await browser.close()
            return None

