import asyncio
import random
from playwright.async_api import async_playwright

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

TEST_URL = "https://miixdrop.net/f/ow90ow8ot6krdg?download"


async def dismiss_overlay(page, log_fn=print):
    """
    تغلق أي overlay ظاهر.
    الـ overlay بيظهر بعد النقرة الأولى مش قبلها.
    
    البنية:
      div.wrapper[data-area="area3"]           ← الـ container
        └── p[data-onopen="0"][data-area="area1"]  ← زر OK
    
    بترجع True لو لقت وغلقت overlay.
    """
    # الـ selector الدقيق لزر OK
    ok_selector = 'p[data-onopen="0"][data-area="area1"]'
    
    try:
        # بنستخدم state="visible" مع timeout قصير جداً
        # لو مش موجود هيرمي exception وبنرجع False
        ok_btn = await page.wait_for_selector(
            ok_selector,
            state="visible",
            timeout=2000  # ثانيتين كافيين
        )
        
        if ok_btn:
            log_fn("🛡️ [Overlay] ظهر الـ overlay! جاري الضغط على OK...")
            # تأخير بشري بسيط
            await page.wait_for_timeout(random.randint(300, 700))
            await ok_btn.click(force=True)
            # انتظر اختفاء الـ overlay
            await page.wait_for_selector(ok_selector, state="hidden", timeout=3000)
            log_fn("✅ [Overlay] تم تجاوز الـ overlay بنجاح!")
            return True
            
    except Exception:
        pass  # مفيش overlay = كويس
    
    return False


async def get_mixdrop_direct_link(embed_url, log_fn=print, headless=True):
    target_url = embed_url.replace("/e/", "/f/")
    if "?download" not in target_url:
        target_url += "?download"

    log_fn(f"🕵️ محاكاة سلوك بشري على: {target_url}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless,
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
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
        )

        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.navigator.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        """)

        page = await context.new_page()
        intercepted_url = {"url": None}

        # مراقبة JSON responses
        async def handle_response(response):
            if "mixdrop" in response.url and "download" in response.url:
                ct = response.headers.get("content-type", "")
                if "application/json" in ct:
                    try:
                        data = await response.json()
                        if data.get("type") == "ok" and "url" in data:
                            intercepted_url["url"] = data["url"]
                            log_fn(f"🎯 [JSON] تم صيد الرابط: {data['url'][:60]}...")
                    except:
                        pass

        page.on("response", handle_response)

        try:
            await page.goto(target_url, wait_until="domcontentloaded")
            await page.wait_for_timeout(1000)

            # فحص 404
            page_content = await page.content()
            if "can't find the file you are looking for" in page_content:
                log_fn("🚫 الرابط ميت: 404")
                await browser.close()
                return "404_DELETED"

            btn_selector = "a.download-btn"

            for i in range(1, 15):
                # لو الرادار صاد الرابط من الـ network
                if intercepted_url["url"]:
                    log_fn(f"🎯 تم صيد الرابط من الشبكة في المحاولة {i}")
                    await browser.close()
                    return intercepted_url["url"]

                try:
                    log_fn(f"🖱️ محاولة {i}: انتظار زر التحميل...")
                    await page.wait_for_selector(btn_selector, state="visible", timeout=12000)

                    # ======================================================
                    # فحص الـ href قبل النقر (لو الرابط جاهز من قبل)
                    # ======================================================
                    btn_href = await page.get_attribute(btn_selector, "href")
                    if btn_href and "mxcontent.net" in btn_href:
                        log_fn(f"✅ الرابط جاهز في الـ DOM: {btn_href[:60]}...")
                        await browser.close()
                        return btn_href

                    # Reload ذكي في المحاولة 6
                    if i == 6:
                        log_fn("🔄 المحاولة 6: Reload للتنشيط...")
                        await page.reload(wait_until="domcontentloaded")
                        await page.wait_for_timeout(3000)
                        continue

                    # ======================================================
                    # تأخير بشري قبل النقر
                    # ======================================================
                    await page.wait_for_timeout(random.randint(1000, 2500))

                    # ======================================================
                    # النقر ومراقبة النوافذ الجديدة
                    # ======================================================
                    try:
                        async with context.expect_page(timeout=8000) as new_page_info:
                            await page.locator(btn_selector).click(force=True)

                        ad_page = await new_page_info.value
                        ad_url = ad_page.url
                        log_fn(f"📺 نافذة جديدة: {ad_url[:60]}...")

                        if "mxcontent" in ad_url or ".mp4" in ad_url:
                            log_fn("🎯 النافذة الجديدة هي رابط التحميل!")
                            intercepted_url["url"] = ad_url
                            await browser.close()
                            return ad_url
                        else:
                            await ad_page.close()

                    except Exception:
                        log_fn(f"ℹ️ النقرة {i} تمت بدون نافذة جديدة.")

                    # ======================================================
                    # ⭐ فحص الـ overlay فوراً بعد النقر ⭐
                    # دا هو التوقيت الصح، مش قبل النقر!
                    # ======================================================
                    overlay_closed = await dismiss_overlay(page, log_fn)
                    if overlay_closed:
                        # بعد إغلاق الـ overlay، دوس تاني على الزر مباشرة
                        log_fn("🔁 إعادة النقر بعد إغلاق الـ overlay...")
                        await page.wait_for_timeout(random.randint(500, 1000))
                        try:
                            async with context.expect_page(timeout=8000) as new_page_info2:
                                await page.locator(btn_selector).click(force=True)
                            ad_page2 = await new_page_info2.value
                            ad_url2 = ad_page2.url
                            log_fn(f"📺 نافذة بعد الـ overlay: {ad_url2[:60]}...")
                            if "mxcontent" in ad_url2 or ".mp4" in ad_url2:
                                intercepted_url["url"] = ad_url2
                                await browser.close()
                                return ad_url2
                            else:
                                await ad_page2.close()
                        except Exception:
                            log_fn("ℹ️ النقرة بعد الـ overlay بدون نافذة.")

                    await page.bring_to_front()

                    # فحص الـ href بعد كل النقرات
                    await page.wait_for_timeout(1500)
                    btn_href = await page.get_attribute(btn_selector, "href")
                    if btn_href and "mxcontent.net" in btn_href:
                        log_fn(f"✅ تم صيد الرابط بعد النقر: {btn_href}...")
                        await browser.close()
                        return btn_href

                    if intercepted_url["url"]:
                        await browser.close()
                        return intercepted_url["url"]

                    log_fn(f"⏳ الرابط لم يظهر بعد...")
                    await page.wait_for_timeout(4000)

                except Exception as e:
                    log_fn(f"⚠️ خطأ في المحاولة {i}: {str(e)[:120]}")
                    continue

            await browser.close()
            return None

        except Exception as e:
            log_fn(f"❌ خطأ عام: {str(e)}")
            await browser.close()
            return None


if __name__ == "__main__":
    # جرب headless=True الأول، لو فشل جرب False
    result = asyncio.run(get_mixdrop_direct_link(TEST_URL, headless=True))
    print(f"\n{'='*50}")
    print(f"النتيجة: {result}")