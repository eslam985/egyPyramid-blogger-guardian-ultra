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

BTN_SELECTOR = "a.download-btn"
OK_SELECTOR  = 'p[data-onopen="0"][data-area="area1"]'
MAX_ATTEMPTS = 14
RELOAD_AT    = 6

STEALTH_SCRIPT = """
    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    window.navigator.chrome = { runtime: {} };
    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
    Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
    var _si = window.setInterval;
    window.setInterval = function(fn, t) {
        try { if (fn.toString().indexOf('debugger') >= 0) return 0; } catch(e) {}
        return _si(fn, t);
    };
    var _st = window.setTimeout;
    window.setTimeout = function(fn, t) {
        try { if (fn.toString().indexOf('debugger') >= 0) return 0; } catch(e) {}
        return _st(fn, t);
    };
"""


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

def _attach_network_interceptor(page, captured: dict):
    """يصطاد رابط التحميل من JSON responses."""

    async def on_response(response):
        url = response.url
        is_mixdrop = "mixdrop" in url or "miixdrop" in url
        is_download = "download" in url
        is_json = "application/json" in response.headers.get("content-type", "")

        if is_mixdrop and is_download and is_json:
            try:
                data = await response.json()
                if data.get("type") == "ok" and "url" in data:
                    captured["url"] = data["url"]
                    log.info(f"🎯 [Network] تم صيد الرابط: {data['url'][:60]}...")
            except Exception:
                pass

    page.on("response", on_response)


# ===========================================================================
# Overlay Handler — نفس منطق اللوكال بالظبط: فحص مباشر بدون wait_for_load_state
# ===========================================================================

async def _find_overlay_frame(page):
    """
    بيفحص الـ main frame + كل الـ iframes مباشرة بدون انتظار.
    نفس منطق test_mixdrop.py اللوكال.
    """
    all_frames = page.frames
    log.info(f"🔍 عدد الـ frames: {len(all_frames)}")

    for i, frame in enumerate(all_frames):
        try:
            url   = frame.url
            count = await frame.locator(OK_SELECTOR).count()
            log.info(f"   Frame[{i}] url={url[:50]}  overlay_count={count}")
            if count > 0:
                el      = frame.locator(OK_SELECTOR).first
                visible = await el.is_visible()
                log.info(f"   ✅ لقينا الـ overlay في Frame[{i}]! visible={visible}")
                return frame
        except Exception as e:
            log.info(f"   Frame[{i}] error: {e}")

    return None


async def _dismiss_overlay(page) -> bool:
    """
    يغلق الـ overlay لو ظهر في أي frame.
    نفس منطق اللوكال: بدون polling loop — فحص مباشر واحد.
    """
    # تعطيل debugger عبر CDP
    try:
        cdp = await page.context.new_cdp_session(page)
        await cdp.send("Debugger.enable")
        await cdp.send("Debugger.setSkipAllPauses", {"skip": True})
    except Exception:
        pass

    frame = await _find_overlay_frame(page)

    if frame is None:
        log.info("ℹ️ [Overlay] مش موجود في أي frame.")
        return False

    log.warning("🛡️ [Overlay] تم رصده! جاري الإغلاق...")

    try:
        # طريقة 1: JS click في الـ frame المحدد
        await frame.evaluate("""
            var btn = document.querySelector('p[data-onopen="0"][data-area="area1"]');
            if (btn) btn.click();
        """)
        await page.wait_for_timeout(800)
        log.info("✅ [Overlay] تم الضغط على OK عبر JS في الـ frame!")

        # هل اختفى؟
        if await frame.locator(OK_SELECTOR).count() == 0:
            log.info("✅ [Overlay] اختفى بعد الـ click!")
            return True

        # طريقة 2: حذف الـ wrapper من الـ DOM
        await frame.evaluate("""
            var w = document.querySelector('div[data-area="area3"]');
            if (w) w.remove();
        """)
        log.info("✅ [Overlay] تم حذفه من الـ DOM!")
        await page.wait_for_timeout(300)
        return True

    except Exception as e:
        log.error(f"⚠️ [Overlay] خطأ أثناء الإغلاق: {e}")
        return False


# ===========================================================================
# Click & Capture — نفس ترتيب اللوكال بالظبط
# ===========================================================================

async def _click_and_capture(page, context, attempt: int, captured: dict) -> str | None:
    """
    نفس منطق test_mixdrop.py:
    1. انقر
    2. لو نافذة → تحقق
    3. فحص overlay بعد النقر مباشرة
    4. لو overlay اتغلق → انقر تاني
    5. فحص href
    """
    # فحص href قبل النقر
    href = await page.get_attribute(BTN_SELECTOR, "href")
    if href and "mxcontent.net" in href:
        log.info(f"✅ الرابط جاهز في الـ DOM: {href[:60]}...")
        return href

    await page.wait_for_timeout(random.randint(800, 1800))

    # النقر الأول مع مراقبة النوافذ
    try:
        async with context.expect_page(timeout=8000) as info:
            await page.locator(BTN_SELECTOR).click(force=True)
        new_page = await info.value
        new_url  = new_page.url
        log.info(f"📺 نافذة جديدة: {new_url[:60]}...")
        if "mxcontent" in new_url or ".mp4" in new_url:
            await new_page.close()
            return new_url
        await new_page.close()
    except Exception:
        log.info(f"ℹ️ النقرة {attempt} بدون نافذة.")

    # فحص الـ overlay بعد النقر مباشرة — نفس اللوكال
    overlay_closed = await _dismiss_overlay(page)
    if overlay_closed:
        log.info("🔁 نقرة ثانية بعد إغلاق الـ overlay...")
        await page.wait_for_timeout(random.randint(400, 900))
        try:
            async with context.expect_page(timeout=8000) as info2:
                await page.locator(BTN_SELECTOR).click(force=True)
            new_page2 = await info2.value
            new_url2  = new_page2.url
            log.info(f"📺 نافذة بعد overlay: {new_url2[:60]}...")
            if "mxcontent" in new_url2 or ".mp4" in new_url2:
                await new_page2.close()
                return new_url2
            await new_page2.close()
        except Exception:
            log.info("ℹ️ نقرة بعد overlay بدون نافذة.")

    # فحص href بعد كل النقرات
    await page.bring_to_front()
    await page.wait_for_timeout(1500)
    href = await page.get_attribute(BTN_SELECTOR, "href")
    if href and "mxcontent.net" in href:
        log.info(f"✅ صيد بعد النقر: {href[:60]}...")
        return href

    return None


# ===========================================================================
# Main Entry Point
# ===========================================================================

async def get_mixdrop_direct_link(embed_url: str) -> str | None:
    """
    يستخرج الرابط المباشر لملف MixDrop.

    Args:
        embed_url: رابط MixDrop (يقبل /e/ أو /f/، ويقبل mixdrop أو miixdrop)

    Returns:
        رابط mxcontent.net المباشر، أو "404_DELETED"، أو None
    """
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
        page    = await context.new_page()

        captured = {"url": None}
        _attach_network_interceptor(page, captured)

        try:
            await page.goto(target_url, wait_until="domcontentloaded")
            await page.wait_for_timeout(1000)

            if "can't find the file you are looking for" in await page.content():
                log.error("🚫 الرابط ميت: الملف محذوف من MixDrop")
                return "404_DELETED"

            for attempt in range(1, MAX_ATTEMPTS + 1):

                if captured["url"]:
                    log.info(f"🎯 تم صيد الرابط من الشبكة في المحاولة {attempt}")
                    return captured["url"]

                log.info(f"🖱️ محاولة {attempt}/{MAX_ATTEMPTS}...")

                try:
                    await page.wait_for_selector(BTN_SELECTOR, state="visible", timeout=12000)
                except Exception:
                    log.warning(f"⚠️ زر التحميل لم يظهر في المحاولة {attempt}")
                    continue

                if attempt == RELOAD_AT:
                    log.warning("🔄 Reload للتنشيط...")
                    await page.reload(wait_until="domcontentloaded")
                    await page.wait_for_timeout(3000)
                    continue

                result = await _click_and_capture(page, context, attempt, captured)
                if result:
                    return result

                if captured["url"]:
                    return captured["url"]

                log.info("⏳ الرابط لم يظهر بعد، ننتظر...")
                await page.wait_for_timeout(4000)

            log.error("❌ استُنفدت كل المحاولات بدون نتيجة")
            return None

        except Exception as e:
            log.error(f"❌ خطأ غير متوقع: {e}")
            return None

        finally:
            await browser.close()