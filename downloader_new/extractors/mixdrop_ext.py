import random
from playwright.async_api import async_playwright
from downloader_new.shared.logger import get_beast_logger

log = get_beast_logger("GuardianUltra")

# ===========================================================================
# Constants
# ===========================================================================

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
]

# زر التحميل الرئيسي
BTN_SELECTOR = "a.download-btn"

# زر OK في الـ overlay (يظهر بعد النقرة الأولى)
OVERLAY_OK_SELECTOR = 'p[data-onopen="0"][data-area="area1"]'

# سكريبت التخفي من الـ Bot Detection
STEALTH_SCRIPT = """
    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    window.navigator.chrome = { runtime: {} };
    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
    Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
"""

MAX_ATTEMPTS = 14
RELOAD_AT_ATTEMPT = 6


# ===========================================================================
# Browser Setup
# ===========================================================================

async def _create_browser(playwright):
    return await playwright.chromium.launch(
        headless=True,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--window-size=1920,1080",
        ],
    )


async def _create_context(browser):
    context = await browser.new_context(
        user_agent=random.choice(USER_AGENTS),
        viewport={"width": 1920, "height": 1080},
        extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
    )
    await context.add_init_script(STEALTH_SCRIPT)
    return context


# ===========================================================================
# Network Interceptor
# ===========================================================================

def _attach_network_interceptor(page, intercepted: dict):
    """يراقب JSON responses ويصطاد رابط التحميل منها."""

    async def on_response(response):
        is_mixdrop = "mixdrop" in response.url or "miixdrop" in response.url
        is_download = "download" in response.url
        is_json = "application/json" in response.headers.get("content-type", "")

        if is_mixdrop and is_download and is_json:
            try:
                data = await response.json()
                if data.get("type") == "ok" and "url" in data:
                    intercepted["url"] = data["url"]
                    log.info(f"🎯 [Network] تم صيد الرابط من JSON: {data['url'][:60]}...")
            except Exception:
                pass

    page.on("response", on_response)


# ===========================================================================
# Overlay Handler
# ===========================================================================

async def _dismiss_overlay(page) -> bool:
    """
    يغلق الـ overlay لو ظهر.

    الـ overlay بيظهر فقط بعد النقرة الأولى على زر التحميل،
    وبيحتوي على زر OK بالـ selector: p[data-onopen="0"][data-area="area1"]

    Returns:
        True  → تم إغلاق الـ overlay
        False → لا يوجد overlay
    """
    try:
        ok_btn = await page.wait_for_selector(
            OVERLAY_OK_SELECTOR,
            state="visible",
            timeout=2000,
        )
        log.warning("🛡️ [Overlay] تم رصد الـ overlay! جاري الضغط على OK...")
        await page.wait_for_timeout(random.randint(300, 700))
        await ok_btn.click(force=True)
        await page.wait_for_selector(OVERLAY_OK_SELECTOR, state="hidden", timeout=3000)
        log.info("✅ [Overlay] تم تجاوز الـ overlay بنجاح!")
        return True
    except Exception:
        return False


# ===========================================================================
# Click & Capture
# ===========================================================================

async def _click_and_capture(page, context, attempt: int, intercepted: dict) -> str | None:
    """
    ينقر على زر التحميل ويحاول يصطاد الرابط من:
    1. الـ href في الـ DOM مباشرة (قبل النقر)
    2. نافذة جديدة إذا فتحت
    3. الـ href في الـ DOM (بعد النقر)

    Returns:
        الرابط المباشر إذا وُجد، أو None
    """
    # --- فحص الـ href قبل النقر (ممكن يكون جاهز من محاولة سابقة) ---
    href_before = await page.get_attribute(BTN_SELECTOR, "href")
    if href_before and "mxcontent.net" in href_before:
        log.info(f"✅ الرابط جاهز في الـ DOM: {href_before[:60]}...")
        return href_before

    # --- تأخير بشري عشوائي ---
    await page.wait_for_timeout(random.randint(1000, 2500))

    # --- النقر مع مراقبة النوافذ الجديدة ---
    try:
        async with context.expect_page(timeout=8000) as new_page_info:
            await page.locator(BTN_SELECTOR).click(force=True)

        new_page = await new_page_info.value
        new_url = new_page.url
        log.info(f"📺 نافذة جديدة: {new_url[:60]}...")

        if "mxcontent" in new_url or ".mp4" in new_url:
            log.info("🎯 النافذة الجديدة هي رابط التحميل!")
            await new_page.close()
            return new_url

        await new_page.close()

    except Exception:
        log.info(f"ℹ️ النقرة {attempt} بدون نافذة جديدة.")

    # --- فحص الـ overlay بعد النقر مباشرة ---
    overlay_closed = await _dismiss_overlay(page)
    if overlay_closed:
        log.info("🔁 إعادة النقر بعد إغلاق الـ overlay...")
        await page.wait_for_timeout(random.randint(500, 1000))
        try:
            async with context.expect_page(timeout=8000) as new_page_info2:
                await page.locator(BTN_SELECTOR).click(force=True)
            new_page2 = await new_page_info2.value
            new_url2 = new_page2.url
            log.info(f"📺 نافذة بعد الـ overlay: {new_url2[:60]}...")
            if "mxcontent" in new_url2 or ".mp4" in new_url2:
                await new_page2.close()
                return new_url2
            await new_page2.close()
        except Exception:
            log.info("ℹ️ النقرة بعد الـ overlay بدون نافذة.")

    # --- فحص الـ href بعد النقر ---
    await page.bring_to_front()
    await page.wait_for_timeout(1500)
    href_after = await page.get_attribute(BTN_SELECTOR, "href")
    if href_after and "mxcontent.net" in href_after:
        log.info(f"✅ تم صيد الرابط بعد النقر: {href_after[:60]}...")
        return href_after

    return None


# ===========================================================================
# Main Entry Point
# ===========================================================================

async def get_mixdrop_direct_link(embed_url: str) -> str | None:
    """
    يستخرج الرابط المباشر لملف MixDrop من رابط الـ embed أو الـ file.

    Args:
        embed_url: رابط MixDrop (يقبل /e/ أو /f/، ويقبل mixdrop أو miixdrop)

    Returns:
        الرابط المباشر (mxcontent.net) أو:
        "404_DELETED" → لو الملف محذوف
        None          → لو فشل الاستخراج
    """
    # --- تجهيز الرابط ---
    target_url = embed_url.replace("miixdrop", "mixdrop").replace("/e/", "/f/")
    if "?download" not in target_url:
        target_url += "?download"

    if "mixdrop" not in target_url:
        log.error(f"❌ رابط غير مدعوم: {target_url}")
        return None

    log.info(f"🕵️ محاكاة سلوك بشري على: {target_url}")

    async with async_playwright() as playwright:
        browser = await _create_browser(playwright)
        context = await _create_context(browser)
        page = await context.new_page()

        intercepted = {"url": None}
        _attach_network_interceptor(page, intercepted)

        try:
            await page.goto(target_url, wait_until="domcontentloaded")
            await page.wait_for_timeout(1000)

            # --- فحص 404 ---
            if "can't find the file you are looking for" in await page.content():
                log.error("🚫 الرابط ميت: الملف محذوف من MixDrop")
                return "404_DELETED"

            # --- الحلقة الرئيسية ---
            for attempt in range(1, MAX_ATTEMPTS + 1):

                # لو الـ network interceptor صاد الرابط
                if intercepted["url"]:
                    log.info(f"🎯 تم صيد الرابط من الشبكة في المحاولة {attempt}")
                    return intercepted["url"]

                log.info(f"🖱️ محاولة {attempt}/{MAX_ATTEMPTS}...")

                try:
                    await page.wait_for_selector(BTN_SELECTOR, state="visible", timeout=12000)
                except Exception:
                    log.warning(f"⚠️ زر التحميل لم يظهر في المحاولة {attempt}")
                    continue

                # --- Reload ذكي ---
                if attempt == RELOAD_AT_ATTEMPT:
                    log.warning("🔄 Reload للتنشيط...")
                    await page.reload(wait_until="domcontentloaded")
                    await page.wait_for_timeout(3000)
                    continue

                # --- النقر ومحاولة صيد الرابط ---
                result = await _click_and_capture(page, context, attempt, intercepted)
                if result:
                    return result

                # لو الـ interceptor صاد شيء أثناء النقر
                if intercepted["url"]:
                    return intercepted["url"]

                log.info(f"⏳ الرابط لم يظهر بعد، ننتظر...")
                await page.wait_for_timeout(4000)

            log.error("❌ استُنفدت كل المحاولات بدون نتيجة")
            return None

        except Exception as e:
            log.error(f"❌ خطأ غير متوقع: {e}")
            return None

        finally:
            await browser.close()