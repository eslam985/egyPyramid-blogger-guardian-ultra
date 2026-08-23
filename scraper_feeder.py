"""
╔══════════════════════════════════════════════════════════════════╗
║          TopCinema Smart Crawler - by Islam                      ║
/media/es/DDrive/projects/apps-python/egyPyramid-guardian-ultra/scraper_feeder.py
╚══════════════════════════════════════════════════════════════════╝
"""

import requests
import json
import re
from bs4 import BeautifulSoup
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

TABLE_TASKS = "download_tasks"
TABLE_MEDIAS = "medias"

MAX_IDLE_BUFFER = 200  # الحد الأقصى للمهام الـ idle في الطابور
TARGET_INSERT = (
    133  # عدد الاعمال المضافة مع كل تشغيله للاسكربت بشرط عدم تخطي MAX_IDLE_BUFFER
)

DELAY_MIN = 3.0  # أقل تأخير (ثانية) بين الأفلام
DELAY_MAX = 7.0  # أعلى تأخير
HEADLESS = True  # False لو عايز تشوف المتصفح

SITE_BASE_URL = "https://topcinemaa.com"
SAFE_PAGE_COUNT = 100  # قيمة احتياطية لو فشل استخراج عدد الصفحات ديناميكياً

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
# IMDb Trailer Resolver
# ===========================================================================


def resolve_imdb_id_from_trailer(trailer_url: str) -> str | None:
    """
    Extract IMDb Title ID (ttxxxxxxx) from an IMDb trailer page.

    Example:
    https://www.imdb.com/videoembed/vi412862233

    returns

    tt9288740
    """

    if not trailer_url:
        return None

    try:

        headers = {
            "User-Agent": (
                "Mozilla/5.0 " "AppleWebKit/537.36 " "Chrome/137 Safari/537.36"
            )
        }

        r = requests.get(
            trailer_url,
            headers=headers,
            timeout=20,
        )

        if r.status_code != 200:
            return None

        soup = BeautifulSoup(r.text, "html.parser")

        script = soup.find("script", id="__NEXT_DATA__")

        if not script:
            return None

        data = json.loads(script.string)

        return data["props"]["pageProps"]["videoEmbedPlaybackData"]["primaryTitle"][
            "id"
        ]

    except Exception as e:

        log.warning(f"Trailer Resolver Error: {e}")

        return None


# ===========================================================================
# Section 4: Duplicate Detection — فحص التكرار
# ===========================================================================


def _is_duplicate_in_tasks(
    sb: Client, movie_name: str, download_url: Optional[str]
) -> bool:
    """فحص التكرار في جدول download_tasks بالاسم أو الرابط."""
    import re

    match = re.search(r"^(.*)\s(\d{4})$", movie_name)
    pure_title = match.group(1).strip() if match else movie_name.strip()

    smart_pattern = re.sub(r"[^a-zA-Z0-9\u0600-\u06FF]+", "%", pure_title)
    smart_pattern = f"%{smart_pattern}%"

    or_filter = f"task_name.ilike.{smart_pattern}"
    if download_url:
        or_filter = f"source_url.eq.{download_url},{or_filter}"

    result = sb.table(TABLE_TASKS).select("id").or_(or_filter).execute()
    return bool(result.data)


def _is_duplicate_in_medias(sb: Client, movie_name: str) -> bool:
    import re

    match = re.search(r"^(.*)\s(\d{4})$", movie_name)
    pure_title = match.group(1).strip() if match else movie_name.strip()
    incoming_year = match.group(2).strip() if match else None

    normalized = normalize_title(pure_title, for_search=False, remove_year=True)

    q = sb.table(TABLE_MEDIAS).select("id").eq("normalized_title", normalized)
    if incoming_year:
        q = q.eq("year", incoming_year)

    return len((q.limit(1).execute().data or [])) > 0


def _is_duplicate_in_tasks(
    sb: Client, movie_name: str, download_url: Optional[str] = None
) -> bool:
    import re

    match = re.search(r"^(.*)\s(\d{4})$", movie_name)
    pure_title = match.group(1).strip() if match else movie_name.strip()
    incoming_year = match.group(2).strip() if match else None

    normalized = normalize_title(pure_title, for_search=False, remove_year=True)

    # 1. شيك بالنورمالايز (ده المهم)
    q = sb.table("download_tasks").select("id").eq("normalized_task_name", normalized)
    if incoming_year:
        q = q.eq("task_year", incoming_year)
    if len((q.limit(1).execute().data or [])) > 0:
        return True

    # 2. شيك برابط الـ embed لو موجود
    if download_url:
        q2 = (
            sb.table("download_tasks")
            .select("id")
            .eq("source_url", download_url)
            .limit(1)
            .execute()
            .data
            or []
        )
        if len(q2) > 0:
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


def insert_task(
    sb: Client,
    movie_name: str,
    download_url: str,
    trailer_url: Optional[str] = None,
    fallback_urls: Optional[list] = None,
) -> bool:
    """إدراج مهمة جديدة في download_tasks مع الـ trailer والـ fallbacks."""
    try:
        payload = {
            "task_name": movie_name,
            "source_url": download_url,
            "status": "idle",
            "progress_percent": 0,
            "download_speed": "0 MB/s",
            "status_message": "Waiting for Beast...",
            "trailer_url": trailer_url,
            "fallback_urls": fallback_urls or [],
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
    anchors = await page.query_selector_all(
        "ul.Posts--List div.Small--Box:not(.Season) a.recent--block"
    )
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


def normalize_title_scraper(title):
    if not title:
        return ""

    t = str(title)

    # تنظيف الرموز - لو للبحث بنسيب النقطتين والشرطة والأبوستروف عشان TMDB/IMDB
    # إزالة ترقيم المواسم والحلقات (S01E05 / S1 / E5)
    t = re.sub(r"\bs\d+\s*e\d+\b", " ", t)
    t = re.sub(r"\bs\d+\b", " ", t)
    t = re.sub(r"\be\d+\b", " ", t)

    stop_words = [
        "مترجمة",
        "مسلسل",
        "فيلم",
        "مترجم",
        "مدبلج",
        "كامل",
        "حصريا",
        "اونلاين",
        "مشاهدة",
        "تحميل",
        "بجودة",
        "عالية",
        "hd",
        "sd",
        "4k",
        "web-dl",
        "bluray",
        "season",
        "episode",
        "سيزون",
        "حلقة",
        "موسم",
        "اون",
        "لاين",
    ]
    for w in stop_words:
        t = re.sub(rf"\b{w}\b", " ", t)

    t = " ".join(t.split())
    return t


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
    return normalize_title_scraper(raw_title)


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


async def _get_iframe_src(page, timeout=15_000) -> Optional[str]:
    try:
        await page.wait_for_selector(".player--iframe iframe[src]", timeout=timeout)
        iframe = await page.query_selector(".player--iframe iframe")
        return (await iframe.get_attribute("src")) if iframe else None
    except:
        return None

async def _extract_mixdrop(page) -> tuple[Optional[str], Optional[str]]:
    servers = await page.query_selector_all(".watch--servers--list ul li.server--item")
    for srv in servers:
        name = (await srv.inner_text()).strip()
        if "Mixdrop" in name or "mixdrop" in name.lower():
            log.info(f"  🎯 محاولة سحب MixDrop: {name}")
            await srv.click()
            await page.wait_for_timeout(2000)

            # فحص رابط ميت
            iframe = await page.query_selector(".player--iframe iframe")
            if iframe:
                frame = await iframe.content_frame()
                if frame:
                    content = await frame.evaluate("document.body.innerHTML")
                    if "can't find the" in content and "looking for" in content:
                        log.error("  🚫 رابط Mixdrop ميت!")
                        return None, "mixdrop_dead"

            src = await _get_iframe_src(page, timeout=15_000)
            if src:
                # الخطأ كان هنا: كان يرجع streamtape_live بدل mixdrop_live
                return src, "mixdrop_live"
    return None, None

async def _extract_streamtape(page) -> tuple[Optional[str], Optional[str]]:
    servers = await page.query_selector_all(".watch--servers--list ul li.server--item")
    for srv in servers:
        name = (await srv.inner_text()).strip()
        if "Streamtape" in name or "streamtape" in name.lower():
            log.info(f"  🎯 محاولة سحب Streamtape: {name}")
            await srv.click()
            await page.wait_for_timeout(2000)

            # فحص رابط ميت
            iframe = await page.query_selector(".player--iframe iframe")
            if iframe:
                frame = await iframe.content_frame()
                if frame:
                    content = await frame.evaluate("document.body.innerHTML")
                    if (
                        "video no longer available" in content.lower()
                        or "not found" in content.lower()
                    ):
                        log.error("  🚫 رابط Streamtape ميت!")
                        return None, "streamtape_dead"

            src = await _get_iframe_src(page, timeout=15_000)
            if src:
                return src, "streamtape_live"
    return None, None

async def _extract_doodstream(page) -> tuple[Optional[str], Optional[str]]:
    servers = await page.query_selector_all(".watch--servers--list ul li.server--item")
    for srv in servers:
        try:
            name = (await srv.inner_text()).strip()
        except Exception:
            continue
        if "Doodstream" in name or "doodstream" in name.lower():
            log.info(f"  🎯 محاولة سحب Doodstream: {name}")
            await srv.click()
            await page.wait_for_timeout(2000)
            src = await _get_iframe_src(page, timeout=8_000)
            if src:
                return src, "doodstream_live"
    return None, None

async def _extract_lulustream(page) -> tuple[Optional[str], Optional[str]]:
    servers = await page.query_selector_all(".watch--servers--list ul li.server--item")
    for srv in servers:
        name = (await srv.inner_text()).strip()
        if "LuluStream" in name or "lulustream" in name.lower():
            log.info(f"  🎯 محاولة سحب LuluStream: {name}")
            await srv.click()
            await page.wait_for_timeout(2000)
            src = await _get_iframe_src(page, timeout=8_000)
            if src:
                return src, "lulstream_live"
    return None, None

async def _extract_streamwish(page) -> tuple[Optional[str], Optional[str]]:
    servers = await page.query_selector_all(".watch--servers--list ul li.server--item")
    for srv in servers:
        name = (await srv.inner_text()).strip()
        if "StreamWish" in name or "streamwish" in name.lower():
            log.info(f"  🎯 محاولة سحب StreamWish: {name}")
            await srv.click()
            await page.wait_for_timeout(2000)
            src = await _get_iframe_src(page, timeout=8_000)
            if src:
                return src, "streamwish_live"
    return None, None

async def _extract_updown(page) -> tuple[Optional[str], Optional[str]]:
    servers = await page.query_selector_all(".watch--servers--list ul li.server--item")
    for srv in servers:
        name = (await srv.inner_text()).strip()
        if "UpDown" in name or "updown" in name.lower():
            log.info(f"  🎯 محاولة سحب UpDown: {name}")
            await srv.click()
            await page.wait_for_timeout(2000)
            src = await _get_iframe_src(page, timeout=8_000)
            if src:
                return src, "updown_live"
    return None, None

async def _extract_filelions(page) -> tuple[Optional[str], Optional[str]]:
    servers = await page.query_selector_all(".watch--servers--list ul li.server--item")
    for srv in servers:
        name = (await srv.inner_text()).strip()
        if "Filelions" in name or "filelions" in name.lower():
            log.info(f"  🎯 محاولة سحب Filelions: {name}")
            await srv.click()
            await page.wait_for_timeout(2000)
            src = await _get_iframe_src(page, timeout=8_000)
            if src:
                return src, "filelions_live"
    return None, None

async def _extract_vidtube(page) -> tuple[Optional[str], Optional[str]]:
    servers = await page.query_selector_all(".watch--servers--list ul li.server--item")
    for srv in servers:
        name = (await srv.inner_text()).strip()
        if "متعدد الجودات" in name or "VideoTube" in name or "videotube" in name.lower():
            log.info(f"  🎯 محاولة سحب VidTube: {name}")
            await srv.click()
            await page.wait_for_timeout(2000)
            src = await _get_iframe_src(page, timeout=8_000)
            if src:
                return src, "vidtube_live"
    return None, None

async def extract_embed_url(page) -> tuple[Optional[str], str, list]:
    """
    يجمع كل الروابط المتاحة ويرجع:
    (primary_url, primary_status, fallback_urls)
    """
    primary_url = None
    primary_status = "none"
    fallbacks = []

    def add_url(src, status):
        nonlocal primary_url, primary_status
        if src:
            if not primary_url:
                primary_url = src
                primary_status = status
            else:
                if src not in fallbacks and src != primary_url:
                    fallbacks.append(src)

    # 1. Streamtape
    log.info("جار البحث عن سرفر Streamtape")
    src, status = await _extract_streamtape(page)
    if status == "streamtape_live":
        log.info(f"✅ Streamtape: {src}")
        add_url(src, status)
    elif status == "streamtape_dead":
        log.warning(f"💀 Streamtape ميت {src}")
    else:
        log.warning("لم يتم العثور ع سرفر Streamtape صالح")

    # 2. MixDrop
    log.info("جار البحث عن سرفر MixDrop")
    src, status = await _extract_mixdrop(page)
    if status == "mixdrop_live":
        log.info(f"✅ MixDrop: {src}")
        add_url(src, status)
    elif status == "mixdrop_dead":
        log.warning(f"💀 MixDrop ميت {src}")
    else:
        log.warning("لم يتم العثور ع سرفر MixDrop صالح")
        
        
    # 8. VidTube
    log.info("جار البحث عن سرفر VidTube")
    src, status = await _extract_vidtube(page)
    if status == "vidtube_live":
        log.info(f"✅ VidTube: {src}")
        add_url(src, status)
    else:
        log.warning("لم يتم العثور ع سرفر VidTube صالح")

    # 3. Doodstream
    log.info("جار البحث عن سرفر Doodstream")
    src, status = await _extract_doodstream(page)
    if status == "doodstream_live":
        log.info(f"✅ Doodstream: {src}")
        add_url(src, status)
    else:
        log.warning("لم يتم العثور ع سرفر Doodstream صالح")

    # 4. StreamWish
    log.info("جار البحث عن سرفر StreamWish")
    src, status = await _extract_streamwish(page)
    if status == "streamwish_live":
        log.info(f"✅ StreamWish: {src}")
        add_url(src, status)
    else:
        log.warning("لم يتم العثور ع سرفر StreamWish صالح")
        
    # 5. LuluStream
    log.info("جار البحث عن سرفر LuluStream")
    src, status = await _extract_lulustream(page)
    if status == "lulstream_live":
        log.info(f"✅ LuluStream: {src}")
        add_url(src, status)
    else:
        log.warning("لم يتم العثور ع سرفر LuluStream صالح")
        
    # 6. UpDown
    log.info("جار البحث عن سرفر UpDown")
    src, status = await _extract_updown(page)
    if status == "updown_live":
        log.info(f"✅ UpDown: {src}")
        add_url(src, status)
    else:
        log.warning("لم يتم العثور ع سرفر UpDown صالح")

    # 7. Filelions
    log.info("جار البحث عن سرفر Filelions")
    src, status = await _extract_filelions(page)
    if status == "filelions_live":
        log.info(f"✅ Filelions: {src}")
        add_url(src, status)
    else:
        log.warning("لم يتم العثور ع سرفر Filelions صالح")
        

    if not primary_url:
        log.error("❌ لم يتم العثور على أي سيرفر صالح.")
        return None, "none", []

    log.info(f"📦 primary: {primary_status} | fallbacks: {len(fallbacks)}")
    return primary_url, primary_status, fallbacks


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
    if idle_count >= MAX_IDLE_BUFFER:
        log.info("🛑 تم إنهاء الجولة: الطابور وصل للحد الأقصى.")
        return True

    if not found_new:
        log.warning("🔄 صفحة مكررة، الانتقال للتالية...")
        return False  # ← دايماً كمّل، الإيقاف بالهدف بس

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
        watch_url = await scrape_watch_url(movie_page)
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
        await watch_page.goto(watch_url, wait_until="domcontentloaded", timeout=40_000)
        await watch_page.wait_for_selector(
            ".watch--servers--list ul li.server--item span", timeout=40_000
        )
        embed_url, server_status, fallback_urls = await extract_embed_url(watch_page)
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
        # بعد
        ok = insert_task(
            sb,
            movie_title,
            embed_url,
            trailer_url=trailer_url,
            fallback_urls=fallback_urls,
        )
        if ok:
            log.info(
                f"  ✅ تم الإدراج بنجاح! | embed: {embed_url} | trailer: {trailer_url}"
            )
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
            try:
                await movie_page.close()
            except:
                pass
        if watch_page:
            try:
                await watch_page.close()
            except:
                pass


def _update_server_stats(stats: dict, server_status: str) -> None:
    """تحديث إحصاءات السيرفرات بناءً على نتيجة الاستخراج."""
    if server_status == "mixdrop_dead":
        stats["mixdrop_dead"] += 1
    elif server_status == "mixdrop_live":
        stats["mixdrop_live"] += 1
    elif server_status == "vidtube_live":
        stats["vidtube_saved"] += 1
    elif server_status == "streamtape_live":
        stats["streamtape_saved"] = stats.get("streamtape_saved", 0) + 1


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
        log.warning(
            f"🛑 الطابور ممتلئ ({idle_count}/{MAX_IDLE_BUFFER}). تم الإيقاف لحماية الروابط."
        )
        return

    log.info("🚀 الطابور جاهز، بدء عملية الصيد والتغذية...")

    # ── إحصاءات الجلسة ───────────────────────────────────────────────
    stats = {
        "inserted": 0,
        "skipped": 0,
        "failed": 0,
        "mixdrop_dead": 0,
        "mixdrop_live": 0,
        "vidtube_saved": 0,
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
            await probe_page.goto(
                build_page_url(1), wait_until="domcontentloaded", timeout=30_000
            )
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
                await list_page.goto(
                    list_url, wait_until="domcontentloaded", timeout=30_000
                )
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
                    log.warning(
                        f"🎯 [Buffer Reached] الطابور امتلأ أثناء فحص الأفلام. إيقاف."
                    )
                    break

                log.info(f"\n  [{idx}/{len(movie_links)}] 🎥 {movie_url}")
                await process_single_movie(browser, sb, movie_url, stats)
                await random_delay()

            # منطق الإيقاف بعد الصفحة
            idle_count = get_idle_tasks_count(sb)
            if stats["inserted"] >= TARGET_INSERT:
                log.info(f"🎯 وصلنا للهدف {TARGET_INSERT} إدراج. إيقاف.")
                break
            if should_stop_after_page(
                crawl_mode, stats["found_new_in_page"], idle_count
            ):
                # في FRESH_NEW مكمّلش، في ARCHIVE_WASH كمّل
                if crawl_mode == "ARCHIVE_WASH":
                    continue  # تخطي صفحة وروح للتالية
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


# ===========================================================================
# Section 13: Series Configuration — إعدادات المسلسلات
# ===========================================================================

SERIES_CATEGORY_URL = "https://topcinemaa.co/category/مسلسلات-اجنبي"
TARGET_SERIES = 1  # عدد المسلسلات الكاملة المستهدفة في كل جلسة
SAFE_SERIES_PAGE_COUNT = 62  # عدد الصفحات الاحتياطي لفئة المسلسلات


# ===========================================================================
# Section 14: Series Scrapers — دوال استخراج بيانات المسلسلات
# ===========================================================================


async def scrape_series_links(page) -> list[str]:
    """استخراج روابط المسلسلات من صفحة الفئة — روابط /series/ فقط."""
    anchors = await page.query_selector_all("a.recent--block")
    links = []
    for a in anchors:
        href = await a.get_attribute("href")
        if href and "/series/" in href:
            links.append(href)
    return links


async def scrape_series_title_and_year(page) -> tuple[str, Optional[str]]:
    """
    استخراج اسم المسلسل والسنة من صفحته الرئيسية.
    السنة من: div.MediaQueryRight > ul.RightTaxContent > li > a[href*='release-year']
    """
    # ── العنوان ──────────────────────────────────────────────────────────
    title_el = await page.query_selector("h1.post-title")
    if title_el:
        raw_title = (await title_el.inner_text()).strip()
    else:
        raw_title = (await page.title()).strip()

    clean = normalize_title_scraper(raw_title)

    # ── السنة ────────────────────────────────────────────────────────────
    year = None
    try:
        year_anchor = await page.query_selector(
            "div.MediaQueryRight ul.RightTaxContent li a[href*='release-year']"
        )
        if year_anchor:
            year_text = (await year_anchor.inner_text()).strip()
            if year_text.isdigit():
                year = year_text
    except Exception:
        pass

    return clean, year


async def scrape_season_links(page) -> list[str]:
    """
    استخراج روابط المواسم من صفحة /list/ الخاصة بالمسلسل.
    كل موسم له رابط /list/ خاص به أيضاً.
    """
    anchors = await page.query_selector_all("ul.Posts--List div.Small--Box.Season a")
    links = []
    for a in anchors:
        href = await a.get_attribute("href")
        if href:
            links.append(href.rstrip("/") + "/list/")
    return links


async def scrape_season_number(page) -> int:
    """استخراج رقم الموسم الحالي من صفحة الموسم."""
    try:
        # نحاول من العنوان
        title_el = await page.query_selector("h1.post-title")
        if title_el:
            text = await title_el.inner_text()
            m = re.search(r"(?:الموسم|موسم|Season)\s*(\d+)", text, re.IGNORECASE)
            if m:
                return int(m.group(1))
        # fallback: من الـ URL
        url = page.url
        m = re.search(r"الموسم[- _]?(\d+)|season[- _]?(\d+)", url, re.IGNORECASE)
        if m:
            return int(m.group(1) or m.group(2))
    except Exception:
        pass
    return 1


async def scrape_episode_links(page) -> list[str]:
    anchors = await page.query_selector_all(
        "ul.Posts--List div.Small--Box:not(.Season) a.recent--block"
    )
    links = []
    for a in anchors:
        href = await a.get_attribute("href")
        if href:
            links.append(href.rstrip("/") + "/watch/")
    return list(reversed(links))


async def scrape_episode_number(page) -> int:
    """استخراج رقم الحلقة من صفحتها."""
    try:
        title_el = await page.query_selector("h1.post-title")
        if title_el:
            text = await title_el.inner_text()
            m = re.search(r"(?:الحلقة|حلقة|ح|Episode)\s*(\d+)", text, re.IGNORECASE)
            if m:
                return int(m.group(1))
        url = page.url
        m = re.search(r"الحلقة[- _]?(\d+)|episode[- _]?(\d+)", url, re.IGNORECASE)
        if m:
            return int(m.group(1) or m.group(2))
    except Exception:
        pass
    return 1


# ===========================================================================
# Section 15: Series Duplicate Check — فحص تكرار الحلقات
# ===========================================================================


def already_exists_episode(
    sb: Client,
    series_name: str,
    season_no: int,
    ep_no: int,
    embed_url: Optional[str] = None,
) -> bool:

    # 1. فحص مباشر بـ embed_url إن وجد
    if embed_url:
        q = (
            sb.table("download_tasks")
            .select("id")
            .eq("source_url", embed_url)
            .limit(1)
            .execute()
        )
        if q.data:
            return True

    # 2. تنظيف الاسم تماماً ليتطابق مع حقل normalized_title في جدول medias (مثل "revenge")
    clean_name = normalize_title(series_name, for_search=False, remove_year=True)

    media = (
        sb.table("medias")
        .select("id")
        .eq("normalized_title", clean_name)
        .limit(1)
        .execute()
    )
    
    if not media.data:
        # بحث بديل بالاسم النظيف حصراً وليس النص الخام
        media = (
            sb.table("medias")
            .select("id")
            .ilike("title", f"%{clean_name}%")
            .limit(1)
            .execute()
        )
        if not media.data:
            return False
            
    media_id = media.data[0]["id"]

    season = (
        sb.table("seasons")
        .select("id")
        .eq("media_id", media_id)
        .eq("season_number", season_no)
        .limit(1)
        .execute()
    )
    if not season.data:
        return False
    season_id = season.data[0]["id"]

    ep = (
        sb.table("episodes")
        .select("id")
        .eq("season_id", season_id)
        .eq("episode_number", ep_no)
        .limit(1)
        .execute()
    )
    return bool(ep.data)

def insert_episode_task(
    sb: Client,
    task_name: str,
    embed_url: str,
    trailer_url: Optional[str] = None,
    fallback_urls: Optional[list] = None,
) -> bool:
    try:
        payload = {
            "task_name": task_name,
            "source_url": embed_url,
            "status": "idle",
            "progress_percent": 0,
            "download_speed": "0 MB/s",
            "status_message": "Waiting for Beast...",
            "trailer_url": trailer_url,
            "fallback_urls": fallback_urls or [],
        }
        sb.table(TABLE_TASKS).insert(payload).execute()
        return True
    except Exception as e:
        log.error(f"❌ خطأ في إدراج الحلقة: {e}")
        return False


# ===========================================================================
# Section 16: Series Processors — معالجة المسلسلات
# ===========================================================================


async def process_single_episode(
    browser,
    sb: Client,
    ep_url: str,
    series_title: str,
    year: Optional[str],
    season_no: int,
    ep_no: int,
    stats: dict,
    trailer_url: Optional[str],
) -> None:
    """معالجة حلقة واحدة: سحب embed → فحص تكرار → إدراج."""
    watch_page = None
    try:
        # ── بناء اسم المهمة ───────────────────────────────────────────
        year_suffix = f" {year}" if year else ""
        task_name = (
            f"مسلسل {series_title} الموسم {season_no} الحلقة {ep_no} مترجم{year_suffix}"
        )
        # ── فحص تكرار مبكر بدون embed ────────────────────────────────
        if already_exists_episode(sb, series_title, season_no, ep_no):
            log.info(f"    ♻️ موجودة مسبقاً: {task_name}")
            stats["ep_skipped"] += 1
            return

        # ── سحب رابط المشاهدة (watch URL) من صفحة الحلقة ────────────
        # الـ ep_url هو رابط /watch/ مباشرةً
        watch_page = await browser.new_page(user_agent=pick_random_agent())
        await watch_page.goto(ep_url, wait_until="domcontentloaded", timeout=40_000)
        await watch_page.wait_for_selector(
            ".watch--servers--list ul li.server--item", timeout=40_000
        )
        embed_url, server_status, fallback_urls = await extract_embed_url(watch_page)
        await watch_page.close()
        watch_page = None

        _update_server_stats(stats, server_status)

        if not embed_url:
            log.warning(f"    ⚠️ لا يوجد embed: {task_name}")
            stats["ep_failed"] += 1
            return

        # ── فحص تكرار نهائي برابط الـ embed ──────────────────────────
        if already_exists_episode(sb, series_title, season_no, ep_no, embed_url):
            log.info(f"    ♻️ الرابط موجود: {task_name}")
            stats["ep_skipped"] += 1
            return

        # ── الإدراج ───────────────────────────────────────────────────
        ok = insert_episode_task(
            sb, task_name, embed_url, trailer_url, fallback_urls=fallback_urls
        )
        if ok:
            log.info(f"    ✅ تم الإدراج: {task_name}")
            stats["ep_inserted"] += 1
        else:
            stats["ep_failed"] += 1

    except PlaywrightTimeout:
        log.error(f"    ⏱️ Timeout: {ep_url}")
        stats["ep_failed"] += 1
    except Exception as exc:
        log.error(f"    ❌ خطأ: {exc}")
        stats["ep_failed"] += 1
    finally:
        if watch_page:
            try:
                await watch_page.close()
            except Exception:
                pass


async def process_single_season(
    browser,
    sb: Client,
    season_list_url: str,
    series_title: str,
    year: Optional[str],
    season_no: int,
    stats: dict,
    trailer_url: Optional[str],
) -> None:
    """معالجة موسم كامل: جلب الحلقات → لوب على كل حلقة."""
    log.info(f"  📺 الموسم {season_no}: {season_list_url}")

    list_page = await browser.new_page(user_agent=pick_random_agent())
    try:
        await list_page.goto(
            season_list_url, wait_until="domcontentloaded", timeout=30_000
        )
        ep_links = await scrape_episode_links(list_page)
    except Exception as exc:
        log.error(f"  ❌ فشل تحميل قائمة حلقات الموسم {season_no}: {exc}")
        ep_links = []
    finally:
        await list_page.close()

    if not ep_links:
        log.warning(f"  ⚠️ لا توجد حلقات في الموسم {season_no}")
        return

    log.info(f"  🎞️ الموسم {season_no} يحتوي {len(ep_links)} حلقة")

    for ep_idx, ep_url in enumerate(ep_links, 1):
        # ── فحص الطابور بعد كل حلقة ──────────────────────────────────
        idle_count = get_idle_tasks_count(sb)
        if idle_count >= MAX_IDLE_BUFFER:
            log.warning(
                f"  🛑 الطابور امتلأ أثناء الموسم {season_no}، "
                f"سيتم إكمال بقية الحلقات ثم الإيقاف."
            )
            # نكمّل الموسم لآخره — الإيقاف بيحصل في process_single_series

        log.info(f"    [{ep_idx}/{len(ep_links)}] 🎬 {ep_url}")
        await process_single_episode(
            browser,
            sb,
            ep_url,
            series_title,
            year,
            season_no,
            ep_idx,
            stats,
            trailer_url,
        )
        await random_delay()


async def process_single_series(
    browser,
    sb: Client,
    series_url: str,
    stats: dict,
) -> bool:
    """
    معالجة مسلسل كامل من البداية للنهاية.
    يُعيد True لو اتضاف شيء جديد، False لو كل حاجة كانت مكررة.
    """
    series_page = None
    try:
        # ── 1. جلب عنوان المسلسل والسنة والتريلر ────────────────────
        series_page = await browser.new_page(user_agent=pick_random_agent())
        await series_page.goto(
            series_url, wait_until="domcontentloaded", timeout=30_000
        )
        series_title, year = await scrape_series_title_and_year(series_page)
        trailer_url = await scrape_trailer_url(series_page)
        await series_page.close()
        series_page = None

        log.info(f"\n{'═'*55}")
        log.info(f"📺 مسلسل: {series_title} ({year or 'سنة غير معروفة'})")

        # ── 2. جلب قائمة المواسم ─────────────────────────────────────
        series_list_url = series_url.rstrip("/") + "/list/"
        list_page = await browser.new_page(user_agent=pick_random_agent())
        try:
            await list_page.goto(
                series_list_url, wait_until="domcontentloaded", timeout=30_000
            )
            season_links = await scrape_season_links(list_page)
        except Exception as exc:
            log.error(f"❌ فشل تحميل قائمة المواسم: {exc}")
            season_links = []
        finally:
            await list_page.close()

        if not season_links:
            log.warning(f"⚠️ لا توجد مواسم: {series_url}")
            stats["series_failed"] += 1
            return False

        log.info(f"📋 عدد المواسم: {len(season_links)}")

        ep_inserted_before = stats["ep_inserted"]
        buffer_full = False

        # ── 3. لوب على المواسم ───────────────────────────────────────
        for season_idx, season_list_url in enumerate(season_links, 1):
            await process_single_season(
                browser,
                sb,
                season_list_url,
                series_title,
                year,
                season_idx,
                stats,
                trailer_url,
            )

            # فحص الطابور بعد كل موسم — لو امتلأ نكمل المسلسل ونوقف بعده
            idle_count = get_idle_tasks_count(sb)
            if idle_count >= MAX_IDLE_BUFFER:
                log.warning(
                    "🛑 الطابور امتلأ بعد الموسم "
                    f"{season_idx}، سيتم إنهاء المسلسل الحالي ثم الإيقاف."
                )
                buffer_full = True
                # نكمل باقي المواسم — الإيقاف بعد return
                continue

        new_eps = stats["ep_inserted"] - ep_inserted_before
        if new_eps > 0:
            log.info(f"✅ اكتمل المسلسل: {series_title} | +{new_eps} حلقة جديدة")
            stats["series_completed"] += 1
        else:
            log.info(f"♻️ المسلسل موجود بالكامل: {series_title}")

        # نُعيد buffer_full عشان المنسق الرئيسي يوقف
        return not buffer_full

    except PlaywrightTimeout:
        log.error(f"⏱️ Timeout في المسلسل: {series_url}")
        stats["series_failed"] += 1
        return True
    except Exception as exc:
        log.error(f"❌ خطأ في المسلسل: {exc}")
        stats["series_failed"] += 1
        return True
    finally:
        if series_page:
            try:
                await series_page.close()
            except Exception:
                pass


# ===========================================================================
# Section 17: Series Main Orchestrator — المنسق الرئيسي للمسلسلات
# ===========================================================================


async def run_series_scraper_async():
    """نقطة الدخول الرئيسية لكراولر المسلسلات."""
    sb = get_supabase()
    log.info("✅ [Series] تم الاتصال بـ Supabase")

    # ── صمام الأمان ───────────────────────────────────────────────────
    idle_count = get_idle_tasks_count(sb)
    log.info(f"🔍 [Series] الطابور الحالي: {idle_count} مهمة idle")
    if idle_count >= MAX_IDLE_BUFFER:
        log.warning(
            f"🛑 [Series] الطابور ممتلئ ({idle_count}/{MAX_IDLE_BUFFER}). إيقاف."
        )
        return

    # ── إحصاءات الجلسة ────────────────────────────────────────────────
    stats = {
        "series_completed": 0,
        "series_failed": 0,
        "ep_inserted": 0,
        "ep_skipped": 0,
        "ep_failed": 0,
        "mixdrop_dead": 0,
        "mixdrop_live": 0,
        "vidtube_saved": 0,
    }

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=HEADLESS,
            args=["--no-sandbox", "--disable-setuid-sandbox"],
        )

        # ── اكتشاف عدد صفحات الفئة ────────────────────────────────────
        probe = await browser.new_page(user_agent=pick_random_agent())
        try:
            await probe.goto(
                SERIES_CATEGORY_URL, wait_until="domcontentloaded", timeout=30_000
            )
            total_pages = await scrape_total_pages(probe)
            log.info(f"📊 [Series] إجمالي صفحات الفئة: {total_pages}")
        except Exception as e:
            total_pages = SAFE_SERIES_PAGE_COUNT
            log.warning(f"⚠️ فشل استخراج عدد الصفحات: {e}")
        finally:
            await probe.close()

        should_stop = False

        # ── الحلقة الرئيسية على الصفحات ──────────────────────────────
        for page_num in range(1, total_pages + 1):
            if should_stop:
                break
            if stats["series_completed"] >= TARGET_SERIES:
                log.info(f"🎯 [Series] وصلنا للهدف {TARGET_SERIES} مسلسل. إيقاف.")
                break

            cat_url = (
                SERIES_CATEGORY_URL
                if page_num == 1
                else f"{SERIES_CATEGORY_URL}/page/{page_num}/"
            )
            log.info(f"\n{'═'*55}")
            log.info(f"📄 [Series] صفحة الفئة {page_num}: {cat_url}")

            # جلب روابط المسلسلات
            cat_page = await browser.new_page(user_agent=pick_random_agent())
            try:
                await cat_page.goto(
                    cat_url, wait_until="domcontentloaded", timeout=30_000
                )
                series_links = await scrape_series_links(cat_page)
            except Exception as exc:
                log.error(f"❌ فشل تحميل صفحة الفئة: {exc}")
                series_links = []
            finally:
                await cat_page.close()

            log.info(f"📺 وجدت {len(series_links)} مسلسل في الصفحة")

            for s_idx, series_url in enumerate(series_links, 1):
                if stats["series_completed"] >= TARGET_SERIES:
                    should_stop = True
                    break

                log.info(f"\n  [{s_idx}/{len(series_links)}] 🎬 {series_url}")
                can_continue = await process_single_series(
                    browser, sb, series_url, stats
                )

                if not can_continue:
                    log.warning("🛑 [Series] الطابور امتلأ بعد اكتمال المسلسل. إيقاف.")
                    should_stop = True
                    break

                await random_delay()

        await browser.close()

    _print_series_summary(stats)


def _print_series_summary(stats: dict) -> None:
    """طباعة ملخص جلسة المسلسلات."""
    log.info(f"\n{'═'*55}")
    log.info("📊 ملخص جلسة المسلسلات:")
    log.info(f"   ✅ مسلسلات اكتملت:              {stats['series_completed']}")
    log.info(f"   ❌ مسلسلات فشلت:                {stats['series_failed']}")
    log.info(f"   🎬 حلقات أُدرجت:                {stats['ep_inserted']}")
    log.info(f"   ♻️  حلقات مكررة تُخطيت:         {stats['ep_skipped']}")
    log.info(f"   ⚠️  حلقات فشلت:                 {stats['ep_failed']}")
    log.info(f"{'─'*55}")
    log.info(f"   💀 روابط Mixdrop البايظة:       {stats['mixdrop_dead']}")
    log.info(f"   🍏 روابط Mixdrop السليمة:       {stats['mixdrop_live']}")
    log.info(f"{'═'*55}")
