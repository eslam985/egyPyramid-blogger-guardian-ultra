# /media/es/DDrive/projects/apps-python/egyPyramid-guardian-ultra/downloader_new/extractors/playwright_ext.py
from playwright.async_api import async_playwright
import asyncio
# الاستدعاء النظيف والمباشر للوجر
from downloader_new.shared.logger import get_beast_logger
from downloader_new.extractors.mixdrop_ext import get_mixdrop_direct_link
from downloader_new.extractors.extract_streamtape import resolve_streamtape

log = get_beast_logger("GuardianUltra")

async def get_direct_link_via_playwright(embed_url):
    # تحويل الرابط للمسار المطلوب
    target_url = embed_url.replace("embed-", "d/").replace(".html", "_h")

    log.info(f"🔍 جاري محاكاة مستخدم حقيقي لصيد الرابط من: {target_url}")

    async with async_playwright() as p:
        # إعدادات المتصفح لتبدو كجهاز حقيقي
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
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
            
            # 🔍 DEBUG: طباعة الـ HTML والعناصر الموجودة
            try:
                html = await page.content()
                log.info(f"📄 HTML snippet:\n{html[:2000]}")
                
                buttons = await page.query_selector_all("a, button")
                for btn in buttons:
                    cls = await btn.get_attribute("class") or ""
                    href = await btn.get_attribute("href") or ""
                    txt = (await btn.inner_text())[:40]
                    if href or "btn" in cls.lower():
                        log.info(f"  🔗 class={cls} | href={href[:60]} | text={txt}")
            except:
                pass
            
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