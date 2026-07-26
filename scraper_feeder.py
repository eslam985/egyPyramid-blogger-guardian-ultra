"""
╔══════════════════════════════════════════════════════════════════╗
║          TopCinema Smart Crawler - by Islam                      ║
║          يجلب روابط LuluStream ويحقنها في Supabase               ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os
import random
import logging
import asyncio
from typing import Optional

import nest_asyncio
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from supabase import create_client, Client

from downloader_new.metadata.formatter import normalize_title

nest_asyncio.apply()


# ===========================================================================
# Section 1: Configuration — الإعدادات المركزية
# ===========================================================================

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

TABLE_TASKS  = "download_tasks"
TABLE_MEDIAS = "medias"

MAX_IDLE_BUFFER = 70    # الحد الأقصى للمهام الـ idle في الطابور
DELAY_MIN       = 3.0   # أقل تأخير (ثانية) بين الأفلام
DELAY_MAX       = 7.0   # أعلى تأخير
HEADLESS        = True  # False لو عايز تشوف المتصفح

SITE_BASE_URL   = "https://topcinemaa.com"
SAFE_PAGE_COUNT = 62    # قيمة احتياطية لو فشل استخراج عدد الصفحات ديناميكياً

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36 Edg/147.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Mobile Safari/537.36",
]


# ===========================================================================
# Section 2: Logging — إعداد الـ Logger
# ===========================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("TopCrawler")


# ===========================================================================
# Section 3: Supabase Client — الاتصال بقاعدة البيانات
# ===========================================================================

def get_supabase() -> Client:
    """إنشاء وإعادة كلاينت Supabase."""
    return create_client(SUPABASE_URL, SUPABASE_KEY)


# ===========================================================================
# Section 4: Duplicate Detection — فحص التكرار
# ===========================================================================

def _is_duplicate_in_tasks(sb: Client, movie_name: str, download_url: Optional[str]) -> bool:
    """فحص التكرار في جدول download_tasks بالاسم أو الرابط."""
    import re
    match = re.search(r"^(.*)\s(\d{4})$", movie_name)
    pure_title = match.group(1).strip() if match else movie_name.strip()

    smart_pattern = re.sub(r'[^a-zA-Z0-9\u0600-\u06FF]+', '%', pure_title)
    smart_pattern = f"%{smart_pattern}%"

    or_filter = f"task_name.ilike.{smart_pattern}"
    if download_url:
        or_filter = f"source_url.eq.{download_url},{or_filter}"

    result = sb.table(TABLE_TASKS).select("id").or_(or_filter).execute()
    return bool(result.data)


def _is_duplicate_in_medias(sb: Client, movie_name: str) -> bool:
    """فحص التكرار في جدول medias بمقارنة العناوين المُنقّاة."""
    import re
    match = re.search(r"^(.*)\s(\d{4})$", movie_name)
    pure_title  = match.group(1).strip() if match else movie_name.strip()
    incoming_year = match.group(2).strip() if match else None

    query = sb.table(TABLE_MEDIAS).select("id,title,year")
    if incoming_year:
        query = query.eq("year", incoming_year)

    rows = query.execute().data or []
    normalized_incoming = normalize_title(pure_title)

    for row in rows:
        if normalize_title(row["title"]) == normalized_incoming:
            log.info(f"♻️ موجود في medias: {row['title']}")
            return True

    return False


def already_exists(sb: Client, movie_name: str, download_url: Optional[str]) -> bool:
    """
    فحص شامل للتكرار في كلا الجدولين.
    يُعيد True لو الفيلم موجود في أي منهما.
    """
    if _is_duplicate_in_tasks(sb, movie_name, download_url):
        log.info(f"♻️ موجود في download_tasks: {movie_name}")
        return True

    if _is_duplicate_in_medias(sb, movie_name):
        return True

    return False


# ===========================================================================
# Section 5: Supabase Write Operations — عمليات الكتابة في DB
# ===========================================================================

def get_idle_tasks_count(sb: Client) -> int:
    """جلب عدد المهام الـ idle الحالية في الطابور."""
    try:
        response = (
            sb.table(TABLE_TASKS)
            .select("id", count="exact")
            .eq("status", "idle")
            .execute()
        )
        return response.count if response.count is not None else 0
    except Exception as e:
        log.error(f"❌ فشل فحص عدد المهام الـ idle: {e}")
        return 999  # رقم كبير كأمان لمنع الـ overflow


def insert_task(sb: Client, movie_name: str, download_url: str, trailer_url: Optional[str] = None) -> bool:
    """إدراج مهمة جديدة في download_tasks مع الـ trailer لو موجود."""
    try:
        payload = {
            "task_name":        movie_name,
            "source_url":       download_url,
            "status":           "idle",
            "progress_percent": 0,
            "download_speed":   "0 MB/s",
            "status_message":   "Waiting for Beast...",
            "trailer_url":      trailer_url,
        }
        sb.table(TABLE_TASKS).insert(payload).execute()
        return True
    except Exception as e:
        log.error(f"❌ خطأ في الإدراج: {e}")
        return False


# ===========================================================================
# Section 6: Page Navigation — التنقل بين الصفحات
# ===========================================================================

def build_page_url(page_num: int) -> str:
    """بناء رابط صفحة القائمة بناءً على رقمها."""
    if page_num == 1:
        return f"{SITE_BASE_URL}/movies/"
    return f"{SITE_BASE_URL}/movies/page/{page_num}/"


def pick_random_agent() -> str:
    """اختيار User-Agent عشوائي."""
    return random.choice(USER_AGENTS)


async def random_delay():
    """تأخير عشوائي بين الطلبات لتجنب الحجب."""
    t = random.uniform(DELAY_MIN, DELAY_MAX)
    log.info(f"💤 انتظار {t:.1f} ثانية...")
    await asyncio.sleep(t)


# ===========================================================================
# Section 7: Page Scrapers — استخراج البيانات من الصفحات
# ===========================================================================

async def scrape_movie_links(page) -> list[str]:
    """استخراج روابط الأفلام من صفحة القائمة."""
    anchors = await page.query_selector_all("a.recent--block")
    links = []
    for a in anchors:
        href = await a.get_attribute("href")
        if href:
            links.append(href)
    return links


async def scrape_total_pages(page) -> int:
    """استخراج رقم آخر صفحة ديناميكياً من أزرار التنقل."""
    try:
        pagination_links = await page.query_selector_all("ul.pagination li a")
        if not pagination_links:
            return SAFE_PAGE_COUNT

        page_numbers = []
        for link in pagination_links:
            text = (await link.inner_text()).strip()
            if text.isdigit():
                page_numbers.append(int(text))

        return max(page_numbers) if page_numbers else SAFE_PAGE_COUNT
    except Exception:
        return SAFE_PAGE_COUNT


async def scrape_movie_title(page) -> str:
    """استخراج وتنظيف عنوان الفيلم من صفحته."""
    title_element = await page.query_selector("h1.post-title")
    if title_element:
        raw_title = (await title_element.inner_text()).strip()
    else:
        raw_title = (
            (await page.title())
            .replace("توب سينما", "")
            .replace("TopCinema", "")
            .strip()
        )
    return normalize_title(raw_title, remove_year=False)


async def scrape_watch_url(page) -> Optional[str]:
    """استخراج رابط صفحة المشاهدة من صفحة الفيلم."""
    watch_anchor = await page.query_selector("a.watch")
    if not watch_anchor:
        return None
    return await watch_anchor.get_attribute("href")


async def scrape_trailer_url(page) -> Optional[str]:
    """
    استخراج رابط التريلر بالضغط على زر المشاهدة وانتظار ظهور الـ iframe.
    يُعيد الـ src مباشرةً أو None لو مفيش تريلر.
    """
    try:
        trailer_btn = await page.query_selector(".ShowTrailerSingle")
        if not trailer_btn:
            log.info("  🎬 لا يوجد زر تريلر في هذه الصفحة.")
            return None

        await trailer_btn.click()
        await page.wait_for_selector(".trailerIFrame iframe", timeout=8_000)

        iframe = await page.query_selector(".trailerIFrame iframe")
        if not iframe:
            return None

        src = await iframe.get_attribute("src")
        log.info(f"  🎬 تم سحب رابط التريلر: {src}")
        return src

    except PlaywrightTimeout:
        log.warning("  ⚠️ انتهت مهلة انتظار iframe التريلر.")
        return None
    except Exception as e:
        log.warning(f"  ⚠️ فشل استخراج التريلر: {e}")
        return None


# ===========================================================================
# Section 8: Embed Extractors — استخراج روابط التشغيل
# ===========================================================================

async def _get_iframe_src(page) -> Optional[str]:
    """انتظار واستخراج src من الـ iframe الرئيسي للمشغل."""
    await page.wait_for_selector(".player--iframe iframe", timeout=15_000)
    iframe = await page.query_selector(".player--iframe iframe")
    return (await iframe.get_attribute("src")) if iframe else None


async def _extract_vidtube(page) -> tuple[Optional[str], Optional[str]]:
    """محاولة استخراج رابط VidTube (متعدد الجودات)."""
    servers = await page.query_selector_all(".watch--servers--list ul li.server--item")
    for srv in servers:
        name = (await srv.inner_text()).strip()
        if "متعدد الجودات" in name:
            log.info(f"  🎯 محاولة سحب VidTube: {name}")
            await srv.click()
            await page.wait_for_timeout(2000)
            src = await _get_iframe_src(page)
            if src:
                return src, "vidtube_live"
    return None, None


async def _extract_mixdrop(page) -> tuple[Optional[str], Optional[str]]:
    """محاولة استخراج رابط MixDrop مع فحص صفحات الـ 404."""
    servers = await page.query_selector_all(".watch--servers--list ul li.server--item")
    for srv in servers:
        name = (await srv.inner_text()).strip()
        if "Mixdrop" not in name:
            continue

        log.info(f"  🎯 محاولة سحب MixDrop: {name}")
        await srv.click()
        await page.wait_for_timeout(2000)

        # فحص رابط ميت في MixDrop
        iframe = await page.query_selector(".player--iframe iframe")
        if iframe:
            frame = await iframe.content_frame()
            if frame:
                content = await frame.evaluate("document.body.innerHTML")
                if "can't find the" in content and "looking for" in content:
                    log.error("  🚫 رابط Mixdrop ميت!")
                    return None, "mixdrop_dead"

        src = await _get_iframe_src(page)
        if src:
            return src, "mixdrop_live"

    return None, None


async def extract_embed_url(page) -> tuple[Optional[str], str]:
    """
    المنسق الرئيسي لاستخراج رابط التشغيل.
    الأولوية: VidTube → MixDrop → فشل.
    """
    src, status = await _extract_vidtube(page)
    if src:
        log.info(f"✅ تم سحب الرابط عبر VidTube: {src}")
        return src, status

    log.warning("⚠️ فشل VidTube، جارٍ تجربة MixDrop...")
    src, status = await _extract_mixdrop(page)
    if src:
        log.info(f"✅ تم سحب الرابط عبر MixDrop: {src}")
        return src, status

    log.error("❌ لم يتم العثور على أي سيرفر صالح.")
    return None, "none"


# ===========================================================================
# Section 9: Crawl Strategy — استراتيجية الزحف
# ===========================================================================

def decide_crawl_mode(total_pages: int) -> tuple[str, int]:
    """
    تحديد نمط الزحف عشوائياً:
    - FRESH_NEW: يبدأ من الصفحة 1 لصيد الحصريات.
    - ARCHIVE_WASH: يبدأ من صفحة عشوائية في العمق لجرف القديم.
    يُعيد: (crawl_mode, start_page).
    """
    mode = random.choice(["FRESH_NEW", "ARCHIVE_WASH"])
    if mode == "FRESH_NEW":
        start_page = 1
        log.info("🎯 [Hybrid Mode: الحصريات] البدء من الصفحة 1 لأحدث الأعمال.")
    else:
        start_page = random.randint(2, total_pages)
        log.info(f"🎲 [Hybrid Mode: الأرشيف] البدء من الصفحة العشوائية: {start_page}")

    return mode, start_page


def should_stop_after_page(crawl_mode: str, found_new: bool, idle_count: int) -> bool:
    """
    منطق إيقاف الزحف بعد نهاية كل صفحة:
    - لو الطابور امتلأ: وقف دائماً.
    - نمط الحصريات + مفيش جديد: وقف (ما بعدها مكرر بالتأكيد).
    - نمط الأرشيف + مفيش جديد: لا تقف، كمّل للصفحة التالية.
    """
    if idle_count >= MAX_IDLE_BUFFER:
        log.info("🛑 تم إنهاء الجولة: الطابور وصل للحد الأقصى.")
        return True

    if crawl_mode == "FRESH_NEW" and not found_new:
        log.warning("⚠️ [Stop Strategy] الصفحة مكررة بالكامل في نمط الحصريات. إنهاء الجولة.")
        return True

    if crawl_mode == "ARCHIVE_WASH" and not found_new:
        log.warning("🔄 [Archive Wash] صفحة مغسولة، الانتقال للتالية...")
        return False

    return False


# ===========================================================================
# Section 10: Movie Processor — معالجة فيلم واحد
# ===========================================================================

async def process_single_movie(
    browser,
    sb: Client,
    movie_url: str,
    stats: dict,
) -> None:
    """
    المسؤول عن معالجة فيلم واحد من البداية للنهاية:
    جلب العنوان → فحص التكرار → سحب الـ embed → سحب التريلر → الإدراج.
    """
    movie_page = None
    watch_page = None

    try:
        # ── 1. جلب العنوان ورابط المشاهدة ──────────────────────────
        movie_page = await browser.new_page(user_agent=pick_random_agent())
        await movie_page.goto(movie_url, wait_until="domcontentloaded", timeout=30_000)

        movie_title = await scrape_movie_title(movie_page)
        watch_url   = await scrape_watch_url(movie_page)
        trailer_url = await scrape_trailer_url(movie_page)

        await movie_page.close()
        movie_page = None

        if not watch_url:
            log.warning("  ⚠️ لم أجد رابط المشاهدة، تخطي...")
            stats["failed"] += 1
            return

        # ── 2. فحص تكرار مبكر بالاسم (قبل فتح صفحة المشاهدة الثقيلة) ──
        if already_exists(sb, movie_title, None):
            log.info(f"  ♻️ [{movie_title}] موجود مسبقاً. تخطي...")
            stats["skipped"] += 1
            return

        log.info(f"  🔗 صفحة المشاهدة: {watch_url}")

        # ── 3. سحب رابط التشغيل (embed) ────────────────────────────
        watch_page = await browser.new_page(user_agent=pick_random_agent())
        await watch_page.goto(watch_url, wait_until="networkidle", timeout=40_000)
        embed_url, server_status = await extract_embed_url(watch_page)
        await watch_page.close()
        watch_page = None

        _update_server_stats(stats, server_status)

        if not embed_url:
            log.warning("  ⚠️ لم أجد رابط الإيمباد أو الرابط ميت، تخطي...")
            stats["failed"] += 1
            return

        # ── 4. فحص تكرار نهائي برابط الـ embed ─────────────────────
        if already_exists(sb, movie_title, embed_url):
            log.info("  ♻️ الرابط موجود مسبقاً، تخطي...")
            stats["skipped"] += 1
            return

        # ── 5. الإدراج في قاعدة البيانات ────────────────────────────
        ok = insert_task(sb, movie_title, embed_url, trailer_url=trailer_url)
        if ok:
            log.info(f"  ✅ تم الإدراج بنجاح! | embed: {embed_url} | trailer: {trailer_url}")
            stats["inserted"] += 1
            stats["found_new_in_page"] = True
        else:
            stats["failed"] += 1

    except PlaywrightTimeout:
        log.error("  ⏱️ انتهت المهلة، تخطي هذا الفيلم...")
        stats["failed"] += 1
    except Exception as exc:
        log.error(f"  ❌ خطأ غير متوقع: {exc}")
        stats["failed"] += 1
    finally:
        if movie_page:
            try: await movie_page.close()
            except: pass
        if watch_page:
            try: await watch_page.close()
            except: pass


def _update_server_stats(stats: dict, server_status: str) -> None:
    """تحديث إحصاءات السيرفرات بناءً على نتيجة الاستخراج."""
    if server_status == "mixdrop_dead":
        stats["mixdrop_dead"] += 1
    elif server_status == "mixdrop_live":
        stats["mixdrop_live"] += 1
    elif server_status == "vidtube_live":
        stats["vidtube_saved"] += 1


# ===========================================================================
# Section 11: Main Orchestrator — المنسق الرئيسي
# ===========================================================================

async def run_scraper_async():
    """نقطة الدخول الرئيسية: تنسق كل شيء من البداية للنهاية."""
    sb = get_supabase()
    log.info("✅ تم الاتصال بـ Supabase")

    # ── صمام الأمان: فحص الطابور قبل البدء ─────────────────────────
    idle_count = get_idle_tasks_count(sb)
    log.info(f"🔍 الطابور الحالي: {idle_count} مهمة idle")

    if idle_count >= MAX_IDLE_BUFFER:
        log.warning(f"🛑 الطابور ممتلئ ({idle_count}/{MAX_IDLE_BUFFER}). تم الإيقاف لحماية الروابط.")
        return

    log.info("🚀 الطابور جاهز، بدء عملية الصيد والتغذية...")

    # ── إحصاءات الجلسة ───────────────────────────────────────────────
    stats = {
        "inserted":          0,
        "skipped":           0,
        "failed":            0,
        "mixdrop_dead":      0,
        "mixdrop_live":      0,
        "vidtube_saved":     0,
        "found_new_in_page": False,
    }

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=HEADLESS,
            args=["--no-sandbox", "--disable-setuid-sandbox"],
        )

        # ── تحديد حجم الموقع ديناميكياً ─────────────────────────────
        probe_page = await browser.new_page(user_agent=pick_random_agent())
        try:
            await probe_page.goto(build_page_url(1), wait_until="domcontentloaded", timeout=30_000)
            total_pages = await scrape_total_pages(probe_page)
            log.info(f"📊 إجمالي الصفحات المكتشفة: {total_pages}")
        except Exception as e:
            total_pages = SAFE_PAGE_COUNT
            log.warning(f"⚠️ فشل استخراج عدد الصفحات، سيتم اعتماد {total_pages}: {e}")
        finally:
            await probe_page.close()

        # ── تحديد استراتيجية الزحف ───────────────────────────────────
        crawl_mode, start_page = decide_crawl_mode(total_pages)

        # ── الحلقة الرئيسية: تمر على الصفحات ────────────────────────
        for page_num in range(start_page, total_pages + 1):

            idle_count = get_idle_tasks_count(sb)
            if idle_count >= MAX_IDLE_BUFFER:
                log.warning(f"🛑 [Buffer Guard] الطابور امتلأ ({idle_count}). إيقاف.")
                break

            list_url = build_page_url(page_num)
            log.info(f"\n{'═' * 55}")
            log.info(f"📄 صفحة القائمة {page_num}: {list_url}")

            # جلب روابط الأفلام من صفحة القائمة
            list_page = await browser.new_page(user_agent=pick_random_agent())
            try:
                await list_page.goto(list_url, wait_until="domcontentloaded", timeout=30_000)
                movie_links = await scrape_movie_links(list_page)
            except Exception as exc:
                log.error(f"❌ فشل تحميل صفحة القائمة: {exc}")
                await list_page.close()
                continue
            finally:
                await list_page.close()

            log.info(f"🎬 وجدت {len(movie_links)} فيلم في الصفحة")
            stats["found_new_in_page"] = False

            # معالجة كل فيلم في الصفحة
            for idx, movie_url in enumerate(movie_links, 1):
                idle_count = get_idle_tasks_count(sb)
                if idle_count >= MAX_IDLE_BUFFER:
                    log.warning(f"🎯 [Buffer Reached] الطابور امتلأ أثناء فحص الأفلام. إيقاف.")
                    break

                log.info(f"\n  [{idx}/{len(movie_links)}] 🎥 {movie_url}")
                await process_single_movie(browser, sb, movie_url, stats)
                await random_delay()

            # منطق الإيقاف بعد الصفحة
            idle_count = get_idle_tasks_count(sb)
            if should_stop_after_page(crawl_mode, stats["found_new_in_page"], idle_count):
                break

            await random_delay()

        await browser.close()

    _print_summary(stats)


# ===========================================================================
# Section 12: Summary Reporter — طباعة ملخص الجلسة
# ===========================================================================

def _print_summary(stats: dict) -> None:
    """طباعة ملخص تفصيلي لنتائج الجلسة."""
    log.info(f"\n{'═' * 55}")
    log.info("📊 ملخص العملية التفصيلي:")
    log.info(f"   ✅ إجمالي المدرج في الـ DB:        {stats['inserted']}")
    log.info(f"   ♻️  أعمال مكررة تم تخطيها:        {stats['skipped']}")
    log.info(f"   ❌ إجمالي الفشل والأخطاء:           {stats['failed']}")
    log.info(f"{'─' * 55}")
    log.info(f"   💀 روابط Mixdrop البايظة:          {stats['mixdrop_dead']}")
    log.info(f"   🍏 روابط Mixdrop السليمة:          {stats['mixdrop_live']}")
    log.info(f"   📺 روابط VidTube المُنقذة:         {stats['vidtube_saved']}")
    log.info(f"{'═' * 55}")