# /media/es/DDrive/projects/apps-python/egyPyramid-guardian-ultra/downloader_new/extractors/playwright_ext.py
from playwright.async_api import async_playwright
# الاستدعاء النظيف والمباشر للوجر
from downloader_new.shared.logger import get_beast_logger
from downloader_new.extractors.mixdrop_ext import get_mixdrop_direct_link
log = get_beast_logger("GuardianUltra")

async def get_direct_link_via_playwright(embed_url):
    # تحويل الرابط للمسار المطلوب
    target_url = embed_url.replace("embed-", "d/").replace(".html", "_h")

    log.info(f"🔍 جاري محاكاة مستخدم حقيقي لصيد الرابط من: {target_url}")

    async with async_playwright() as p:
        # إعدادات المتصفح لتبدو كجهاز حقيقي
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        try:
            # 1. الذهاب للصفحة
            await page.goto(target_url, wait_until="networkidle", timeout=45000)

            # 2. التعامل مع العداد التنازلي (لو موجود)
            # هننتظر الزرار يظهر حتى لو اتأخر 15 ثانية
            btn_selector = "a.btn-gradient.submit-btn"

            log.info("⏳ ننتظر ظهور زر التحميل (قد يستغرق 10 ثوانٍ بسبب العداد)...")
            await page.wait_for_selector(btn_selector, state="visible", timeout=20000)

            # 3. استخراج الرابط
            direct_link = await page.get_attribute(btn_selector, "href")

            # تأكيد إضافي: لو الرابط عبارة عن "javascript:void(0)" أو "#"
            # ده معناه إنه بيحتاج "نقرة" لتوليده
            if (
                not direct_link
                or direct_link.startswith("#")
                or "javascript" in direct_link
            ):
                log.info("🖱️ الرابط يحتاج لنقرة لتوليده، جاري النقر...")
                await page.click(btn_selector)
                # ننتظر ثانية لتحديث الرابط
                await page.wait_for_timeout(2000)
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
    في حالة mixdrop 404، يرمي Exception.
    تعيد الرابط المباشر أو الرابط الأصلي إذا فشلت المعالجة.
    """
    if "vidtube.one" in raw_url or "cdn-tube" in raw_url:
        log.info("🎯 تم اكتشاف رابط VidTube/Lulu.. جاري استخراج الرابط المباشر...")
        direct_link = await get_direct_link_via_playwright(raw_url)
        if direct_link:
            log.info(f"✅ تم صيد الرابط بنجاح! سيتم التحميل الآن.")
            return direct_link
        else:
            log.warning("⚠️ فشل الصيد، سنحاول بالرابط الأصلي (قد يفشل).")
            return raw_url

    elif "mixdrop" in raw_url:
        log.info("🎯 تم اكتشاف رابط MixDrop.. جاري الصيد من صفحة التحميل...")
        direct_link = await get_mixdrop_direct_link(raw_url)
        if direct_link == "404_DELETED":
            raise Exception("الملف محذوف نهائياً من المصدر (MixDrop 404)")
        if direct_link:
            log.info(f"✅ تم صيد رابط MixDrop المباشر بنجاح.")
            return direct_link
        else:
            log.warning("⚠️ فشل الصيد، سنحاول بالرابط الأصلي (قد يفشل).")
            return raw_url

    return raw_url
