import asyncio
import random
from playwright.async_api import async_playwright

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
]

TEST_URL     = "https://miixdrop.net/f/ow90ow8ot6krdg?download"
BTN_SELECTOR = "a.download-btn"
OK_SELECTOR  = 'p[data-onopen="0"][data-area="area1"]'


# ===========================================================================
# أين يعيش الـ overlay؟ — بنفحص كل الـ frames
# ===========================================================================
async def find_overlay_frame(page):
    """
    بيفحص الـ main frame + كل الـ iframes
    ويرجع (frame, element) لو لقى الـ overlay أو (None, None)
    """
    all_frames = page.frames
    print(f"🔍 عدد الـ frames: {len(all_frames)}")

    for i, frame in enumerate(all_frames):
        try:
            url   = frame.url
            count = await frame.locator(OK_SELECTOR).count()
            print(f"   Frame[{i}] url={url[:50]}  overlay_count={count}")
            if count > 0:
                el = frame.locator(OK_SELECTOR).first
                visible = await el.is_visible()
                print(f"   ✅ لقينا الـ overlay في Frame[{i}]! visible={visible}")
                return frame, el
        except Exception as e:
            print(f"   Frame[{i}] error: {e}")

    return None, None


# ===========================================================================
# Dismiss overlay — بيدور في كل الـ frames
# ===========================================================================
async def dismiss_overlay(page):
    # تعطيل debugger عبر CDP
    try:
        cdp = await page.context.new_cdp_session(page)
        await cdp.send("Debugger.enable")
        await cdp.send("Debugger.setSkipAllPauses", {"skip": True})
    except Exception:
        pass

    frame, el = await find_overlay_frame(page)

    if frame is None:
        print("ℹ️ [Overlay] مش موجود في أي frame.")
        return False

    try:
        # طريقة 1: JS click في الـ frame المحدد
        await frame.evaluate("""
            var btn = document.querySelector('p[data-onopen="0"][data-area="area1"]');
            if (btn) btn.click();
        """)
        await page.wait_for_timeout(800)
        print("✅ [Overlay] تم الضغط على OK عبر JS في الـ frame!")

        # تحقق من الاختفاء
        still = await frame.locator(OK_SELECTOR).count()
        if still == 0:
            print("✅ [Overlay] اختفى!")
            return True

        # طريقة 2: إزالة الـ wrapper من الـ DOM
        await frame.evaluate("""
            var w = document.querySelector('div[data-area="area3"]');
            if (w) w.remove();
        """)
        print("✅ [Overlay] تم حذفه من الـ DOM!")
        await page.wait_for_timeout(300)
        return True

    except Exception as e:
        print(f"⚠️ dismiss error: {e}")
        return False


# ===========================================================================
# Main
# ===========================================================================
async def get_mixdrop_direct_link(embed_url, headless=False):
    target_url = embed_url.replace("/e/", "/f/")
    if "?download" not in target_url:
        target_url += "?download"

    print(f"🕵️ على: {target_url}")

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
            var _si = window.setInterval;
            window.setInterval = function(fn,t){
                try{ if(fn.toString().indexOf('debugger')>=0) return 0; }catch(e){}
                return _si(fn,t);
            };
            var _st = window.setTimeout;
            window.setTimeout = function(fn,t){
                try{ if(fn.toString().indexOf('debugger')>=0) return 0; }catch(e){}
                return _st(fn,t);
            };
        """)

        page     = await context.new_page()
        captured = {"url": None}

        async def on_response(response):
            url = response.url
            if ("mixdrop" in url or "miixdrop" in url) and "download" in url:
                if "application/json" in response.headers.get("content-type", ""):
                    try:
                        data = await response.json()
                        if data.get("type") == "ok" and "url" in data:
                            captured["url"] = data["url"]
                            print(f"🎯 [Network] {data['url'][:60]}...")
                    except Exception:
                        pass

        page.on("response", on_response)

        try:
            await page.goto(target_url, wait_until="domcontentloaded")
            await page.wait_for_timeout(1500)

            if "can't find the file you are looking for" in await page.content():
                return "404_DELETED"

            for attempt in range(1, 15):
                if captured["url"]:
                    print(f"🎯 صيد من الشبكة في المحاولة {attempt}")
                    return captured["url"]

                try:
                    await page.wait_for_selector(BTN_SELECTOR, state="visible", timeout=12000)
                except Exception:
                    continue

                # فحص الـ href قبل النقر
                href = await page.get_attribute(BTN_SELECTOR, "href")
                if href and "mxcontent.net" in href:
                    print(f"✅ الرابط في الـ DOM: {href[:60]}...")
                    return href

                if attempt == 6:
                    print("🔄 Reload...")
                    await page.reload(wait_until="domcontentloaded")
                    await page.wait_for_timeout(3000)
                    continue

                print(f"🖱️ محاولة {attempt}...")
                await page.wait_for_timeout(random.randint(800, 1800))

                # النقر الأول
                try:
                    async with context.expect_page(timeout=8000) as info:
                        await page.locator(BTN_SELECTOR).click(force=True)
                    new_p = await info.value
                    new_u = new_p.url
                    print(f"📺 نافذة: {new_u[:60]}...")
                    if "mxcontent" in new_u or ".mp4" in new_u:
                        await new_p.close()
                        return new_u
                    await new_p.close()
                except Exception:
                    print(f"ℹ️ بدون نافذة.")

                # --- فحص الـ overlay في كل الـ frames ---
                closed = await dismiss_overlay(page)
                if closed:
                    print("🔁 نقرة ثانية بعد إغلاق الـ overlay...")
                    await page.wait_for_timeout(random.randint(400, 900))
                    try:
                        async with context.expect_page(timeout=8000) as info2:
                            await page.locator(BTN_SELECTOR).click(force=True)
                        new_p2 = await info2.value
                        new_u2 = new_p2.url
                        print(f"📺 نافذة بعد overlay: {new_u2[:60]}...")
                        if "mxcontent" in new_u2 or ".mp4" in new_u2:
                            await new_p2.close()
                            return new_u2
                        await new_p2.close()
                    except Exception:
                        print("ℹ️ نقرة بعد overlay بدون نافذة.")

                await page.bring_to_front()
                await page.wait_for_timeout(1500)

                href = await page.get_attribute(BTN_SELECTOR, "href")
                if href and "mxcontent.net" in href:
                    print(f"✅ صيد بعد النقر: {href[:60]}...")
                    return href

                if captured["url"]:
                    return captured["url"]

                print(f"⏳ لم يظهر بعد...")
                await page.wait_for_timeout(4000)

            print("❌ استُنفدت كل المحاولات")
            return None

        except Exception as e:
            print(f"❌ خطأ: {e}")
            return None
        finally:
            await browser.close()


if __name__ == "__main__":
    result = asyncio.run(get_mixdrop_direct_link(TEST_URL, headless=False))
    print(f"\n{'='*50}\nالنتيجة: {result}")