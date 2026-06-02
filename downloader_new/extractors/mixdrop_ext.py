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

        # تشغيل المتصفح لاستخراج الرابط
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--window-size=1920,1080",
            ],
        )
        context = await browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport={"width": 1920, "height": 1080},
        )
        page = await context.new_page()
        #زرع مراقب الشبكة (Network Interceptor) لصيد الـ JSON
        # متغير لتخزين الرابط لو تم إرجاعه عبر POST Request
        intercepted_url = {"url": None}

        async def handle_response(response):
            if "?download" in response.url and response.request.method == "POST":
                try:
                    json_data = await response.json()
                    if json_data.get("type") == "ok" and json_data.get("url"):
                        intercepted_url["url"] = json_data["url"]
                        print(f"📡 تم التقاط الرابط من الـ Network: {intercepted_url['url'][:60]}...")
                except:
                    pass

        page.on("response", handle_response)

        try:
            await page.goto(target_url, wait_until="domcontentloaded")

            # --- 🔍 فحص هل الملف محذوف فعلياً من المصدر ---
            page_content = await page.content()
            if "can't find the file you are looking for" in page_content:
                log.error("🚫 الرابط ميت: MixDrop بيقول We can't find the file")
                await browser.close()
                return "404_DELETED"

            # --- 🛡️ تجاوز الـ Brave Alert / Interstitial ---
            # حذفنا كلمة button ليصطاد العنصر سواء كان p أو div أو button
            ok_btn_selector = '[data-area="area1"]'
            try:
                log.info("⏳ جاري فحص وجود غلاف الحماية (Brave Alert أو غيره)...")
                ok_btn = await page.wait_for_selector(ok_btn_selector, state="visible", timeout=7000)
                if ok_btn:
                    log.info("🛡️ تم رصد الغلاف المغطي للزر.. جاري المحاكاة وتخطيه...")
                    await page.mouse.move(random.randint(100, 500), random.randint(100, 500))
                    await page.wait_for_timeout(1500)
                    
                    # استخدام force=True لضمان الضغط حتى لو كان هناك طبقة شفافة فوقه
                    await ok_btn.click(force=True)
                    log.info("✅ تم الضغط على زر التأكيد (حسنا/OK)، ننتظر التفاعل وبناء الـ Session...")
                    await page.wait_for_timeout(random.randint(4000, 6000))
            except Exception as e:
                log.info(f"⏩ لم يظهر غلاف الحماية: {str(e)}")

            btn_selector = "a.download-btn"

            for i in range(1, 11):
                if intercepted_url["url"]:
                    log.info(f"🎯 تم صيد الرابط من الشبكة في المحاولة {i}")
                    await browser.close()
                    return intercepted_url["url"]

                try:
                    log.info(f"🖱️ محاولة فحص زر التحميل رقم {i}...")
                    await page.wait_for_selector(btn_selector, state="visible", timeout=12000)
                    # --- ⚡ تعديل الـ Reload الذكي ⚡ ---
                    if i == 5:
                        print(
                            "🔄 الموقع يبدو متجمداً.. جاري إعادة تحميل الصفحة (Reload) للتنشيط..."
                        )
                        await page.reload(wait_until="domcontentloaded")
                        await page.wait_for_timeout(3000)
                        continue
                    # ----------------------------------
                    try:
                        async with context.expect_page(timeout=8000) as new_page_info:
                            await page.click(btn_selector)
                        
                        ad_page = await new_page_info.value
                        log.info("📺 إعلان ظهر (Pop-up)، جاري إغلاقه...")
                        await ad_page.close()
                    except Exception:
                        log.info(f"⚠️ النقرة {i} لم تفتح نافذة منبثقة.")
                    # ----------------------------------

                    await page.bring_to_front()

                    # التحقق أولاً مما إذا كان الرابط قد وصل كـ JSON في الـ Background
                    if intercepted_url["url"]:
                        print("✅ تم استخراج الرابط المباشر من استجابة الخادم بنجاح.")
                        await browser.close()
                        return intercepted_url["url"]

                    # فحص الرابط المباشر في الـ href كبديل احتياطي (Fallback)
                    href = await page.get_attribute(btn_selector, "href")

                    if href and href.startswith("http"):
                        # فحص ذكي: هل الرابط يحتوي على كلمة mxcontent (بأي شكل) أو ليس له علاقة بـ mixdrop؟
                        is_valid_direct = "mxcontent" in href or (
                            not ("?download" in href or "mixdrop" in href)
                        )

                        if is_valid_direct:
                            print(f"✅ تم صيد الرابط بنجاح: {href[:60]}...")

                            await browser.close()
                            return href

                    print("⏳ الرابط لم يظهر بعد، ننتظر ثواني للنقرة التالية...")
                    await page.wait_for_timeout(
                        5000
                    )  # زودنا الانتظار لـ 5 ثواني عشان ندي فرصة للسيرفر
                except Exception as e:
                    print(f"⚠️ خطأ في المحاولة {i}: {str(e)}")
                    continue  # لو محاولة فشلت يكمل للي بعدها ميفصلش السكريبت

            await browser.close()
            return None

        except Exception as e:
            print(f"❌ خطأ أثناء المحاكاة البشرية: {str(e)}")
            await browser.close()
            return None
