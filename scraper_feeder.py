"""
╔══════════════════════════════════════════════════════════════════╗
║          TopCinema Smart Crawler - by Islam                      ║
║          يجلب روابط LuluStream ويحقنها في Supabase               ║
╚══════════════════════════════════════════════════════════════════╝
/media/es/DDrive/projects/apps-python/egyPyramid-guardian-ultra/scraper_feeder.py
المتطلبات (شغّل في Colab):
    !pip install playwright supabase-py
    !playwright install chromium

الإعدادات: عدّل القسم CONFIG أدناه فقط.
"""

import os
import time
import random
import logging
from typing import Optional
import re
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from supabase import create_client, Client
import nest_asyncio
import asyncio

# هذا السطر هو السحر الذي يحل المشكلة في كولاب
nest_asyncio.apply()

# ──────────────────────────────────────────────
# ⚙️  CONFIG — عدّل هنا فقط
# ──────────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
TABLE_NAME = "download_tasks"

# تم إلغاء أرقام الصفحات الثابتة لتعمل ديناميكياً بالكامل
MAX_IDLE_BUFFER = 1  # الحد الأقصى للمهام الـ idle في الطابور لحماية الروابط من الموت

DELAY_MIN = 3.0  # أقل تأخير (ثانية) بين الأفلام
DELAY_MAX = 7.0  # أعلى تأخير

HEADLESS = True  # False لو عايز تشوف المتصفح

# ──────────────────────────────────────────────
# 🪵  Logging
# ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("TopCrawler")

# ──────────────────────────────────────────────
# 🎭  User-Agents عشوائية
# ──────────────────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) "
    "Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
]


# ──────────────────────────────────────────────
# 🗄️  Supabase helpers
# ──────────────────────────────────────────────
def get_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def already_exists(sb: Client, movie_name: str, download_url: str) -> bool:
    """
    فحص ذكي للتكرار يعالج تلوث العناوين بالسنين واختلاف حالة الأحرف.
    """
    # 1. تنظيف أولي لاسم الفيلم القادم من البوت (إزالة السنة لو ملتصقة بالاسم)
    # نستخدم نفس منطق normalize_title لضمان أننا نبحث عن "الاسم الصافي"
    import re

    # فصل السنة عن الاسم إذا كان movie_name يحتوي عليها في آخره
    match = re.search(r"^(.*)\s(\d{4})$", movie_name)
    if match:
        incoming_pure_title = match.group(1).strip()
        incoming_year = match.group(2).strip()
    else:
        incoming_pure_title = movie_name.strip()
        incoming_year = None

    # 2. الفحص في جدول المهام (download_tasks)
    # نستخدم ilike ليتجاهل الكابتل والاسمول تلقائياً
    in_tasks = (
        sb.table("download_tasks")
        .select("id")
        .or_(f"source_url.eq.{download_url},task_name.ilike.{movie_name}")
        .execute()
    )

    if in_tasks.data:
        return True

    # 3. الفحص في جدول الميديا (medias) - الاستراتيجية القاتلة
    # سنقوم بالبحث عن الاسم الصافي بدون السنة
    query = sb.table("medias").select("id").ilike("title", incoming_pure_title)

    # لو عندنا سنة، نضيق البحث بها لزيادة الدقة
    if incoming_year:
        query = query.eq("year", incoming_year)

    in_medias = query.execute()

    if in_medias.data:
        log.info(
            f"  ♻️  تم العثور على الفيلم في الميديا (تكرار): {incoming_pure_title}"
        )
        return True

    # 4. فحص احتياطي (لو العنوان في القاعدة فيه سنة محشورة بالخطأ)
    # نبحث عن الاسم متبوعاً بأي شيء (Wildcard)
    in_medias_wildcard = (
        sb.table("medias").select("id").ilike("title", f"%{incoming_pure_title}%")
    )
    if incoming_year:
        in_medias_wildcard = in_medias_wildcard.eq("year", incoming_year)

    res_wildcard = in_medias_wildcard.execute()
    if res_wildcard.data:
        log.info(f"  ♻️  تطابق Wildcard (تكرار محتمل): {incoming_pure_title}")
        return True

    return False


def insert_task(sb: Client, movie_name: str, download_url: str) -> bool:
    """يُدرج مهمة جديدة في download_tasks."""
    try:
        sb.table(TABLE_NAME).insert(
            {
                "task_name": movie_name,
                "source_url": download_url,
                "status": "idle",
                "progress_percent": 0,
                "download_speed": "0 MB/s",
                "status_message": "Waiting for Beast...",
            }
        ).execute()
        return True
    except Exception as exc:
        log.error(f"  ❌ خطأ في الإدراج: {exc}")
        return False


def get_idle_tasks_count(sb) -> int:
    """استعلام سريع لجلب عدد المهام المنتظرة حالياً في الطابور"""
    try:
        response = (
            sb.table(TABLE_NAME)
            .select("id", count="exact")
            .eq("status", "idle")
            .execute()
        )
        # إذا نجح الاستعلام نُرجع العدد الفعلي، وإلا نُرجع 0 كأمان
        return response.count if response.count is not None else 0
    except Exception as e:
        log.error(f"❌ فشل فحص عدد المهام الـ idle من قاعدة البيانات: {e}")
        # لو حصل خطأ في الاتصال نرجع رقم كبير كأمان عشان الاسكربت ما يغرقش الطابور بالخطأ
        return 999


# ──────────────────────────────────────────────
# 🕷️  Crawler Logic
# ──────────────────────────────────────────────
def build_page_url(page_num: int) -> str:
    if page_num == 1:
        return "https://topcinemaa.com/movies/"
    return f"https://topcinemaa.com/movies/page/{page_num}/"


async def get_movie_links(page) -> list[str]:
        """يسحب روابط الأفلام من صفحة القائمة."""
        anchors = await page.query_selector_all("a.recent--block")
        links = []
        for a in anchors:
            href = await a.get_attribute("href")
            if href:
                links.append(href)
        return links


async def get_watch_url(page) -> Optional[str]:
        """يسحب رابط صفحة المشاهدة (/watch/) من صفحة الفيلم."""
        watch_anchor = await page.query_selector("a.watch")
        if not watch_anchor:
            return None
        return await watch_anchor.get_attribute("href")

"""
async def get_embed_url(page) -> tuple[Optional[str], str]:

    # 1) ابحث عن السيرفر المطلوب في القائمة
    servers = await page.query_selector_all(".watch--servers--list ul li.server--item")

    target_btn = None
    for server in servers:
        name = (await server.inner_text()).strip()
        # بنبحث عن "متعدد الجودات" أو "Mixdrop" لضمان الصيد في كل الحالات
        if "Mixdrop" in name:
            target_btn = server
            log.info(f"  🎯 وجدنا السيرفر المطلوب: {name}")
            break

    if not target_btn:
        log.warning("  ⚠️  لم يتم العثور على سيرفر Mixdrop في القائمة")
        return None, "none"

    # 2) النقر على السيرفر
    await target_btn.click()
    log.info("  🖱️  تم النقر على Mixdrop ننتظر تحديث المشغل...")

    # 3) الانتظار الذكي
    try:
        # بننتظر الـ iframe يظهر عموماً أولاً
        await page.wait_for_selector(".player--iframe iframe", timeout=15_000)

        # بنعمل حلقة تكرار صغيرة (Loop) لمدة 5 ثواني للتأكد إن الـ SRC اتغير لـ Mixdrop
        # لأن أحياناً الـ iframe بيفضل موجود بس الـ SRC هو اللي بيتغير
        for _ in range(10):
            iframe = await page.query_selector(".player--iframe iframe")
            src = (await iframe.get_attribute("src")) if iframe else ""

            if "mixdrop" in src:
                # الدخول داخل محتوى الـ iframe نفسه لفحص النصوص المكتوبة داخله
                iframe_element = await page.query_selector(".player--iframe iframe")
                if iframe_element:
                    try:
                        frame = await iframe_element.content_frame()
                        if frame:
                            await page.wait_for_timeout(1000)
                            # جلب المحتوى باستخدام evaluate بدلاً من content غير الموجودة
                            frame_content = await frame.evaluate("document.body.innerHTML")
                            # فحص مرن يغطي الصيغتين (file أو video) أو وجود نص WE ARE SORRY الشهير
                            if (
                                "can't find the" in frame_content
                                and "looking for" in frame_content
                            ):
                                log.error(
                                    f"  🚫 رابط Mixdrop ميت ({src})! جاري الانتقال للخطة البديلة (سيرفر متعدد الجودات)..."
                                )

                                # --- 🔄 الخطة البديلة (Fallback) ---
                                fallback_btn = None
                                all_servers = await page.query_selector_all(
                                    ".watch--servers--list ul li.server--item"
                                )
                                for srv in all_servers:
                                    srv_name = (await srv.inner_text()).strip()
                                    if "متعدد الجودات" in srv_name:
                                        fallback_btn = srv
                                        log.info(
                                            f"  🎯 وجدنا السيرفر البديل: {srv_name}"
                                        )
                                        break

                                if fallback_btn:
                                    await fallback_btn.click()
                                    log.info(
                                        "  🖱️ تم النقر على متعدد الجودات، ننتظر الرابط البديل..."
                                    )
                                    await page.wait_for_timeout(2000)  # انتظار للتحميل
                                    alt_iframe = await page.query_selector(
                                        ".player--iframe iframe"
                                    )
                                    alt_src = (await alt_iframe.get_attribute("src")) if alt_iframe else ""
                                    if alt_src:
                                        log.info(
                                            f"  🔗 تم إنقاذ الفيلم واصطياد الرابط البديل بنجاح: {alt_src}"
                                        )
                                        return alt_src, "vidtube_fallback"

                                # لو حتى البديل مش موجود أو فشل
                                return "404_DELETED", "mixdrop_dead_no_fallback"
                    except Exception as e:
                        log.warning(
                            f"  ⚠️ فشل فحص محتوى الـ iframe الداخلي أو الـ Fallback: {str(e)}"
                        )

                log.info(f"  🔗 تم اصطياد الرابط بنجاح: {src}")
                return src, "mixdrop_live"

            await page.wait_for_timeout(500)  # انتظر نص ثانية وجرب تاني

    except PlaywrightTimeout:
        log.warning("  ⏱️  انتهت المهلة: سيرفر Mixdrop لم يستجب")

    return None, "none"
"""
# --- دالة مساعدة عامة ---
async def get_iframe_src(page):
    """انتظار الحصول على الـ iframe واستخراج الرابط منه."""
    await page.wait_for_selector(".player--iframe iframe", timeout=15_000)
    iframe = await page.query_selector(".player--iframe iframe")
    return (await iframe.get_attribute("src")) if iframe else None

# --- معالج سيرفر VidTube (الأولوية الأولى) ---
async def extract_vidtube(page):
    servers = await page.query_selector_all(".watch--servers--list ul li.server--item")
    for srv in servers:
        name = (await srv.inner_text()).strip()
        if "متعدد الجودات" in name:
            log.info(f"  🎯 محاولة سحب VidTube/متعدد الجودات: {name}")
            await srv.click()
            await page.wait_for_timeout(2000)
            src = await get_iframe_src(page)
            if src: return src, "vidtube_live"
    return None, None

# --- معالج سيرفر MixDrop (الأولوية الثانية) ---
async def extract_mixdrop(page):
    servers = await page.query_selector_all(".watch--servers--list ul li.server--item")
    for srv in servers:
        name = (await srv.inner_text()).strip()
        if "Mixdrop" in name:
            log.info(f"  🎯 محاولة سحب MixDrop: {name}")
            await srv.click()
            await page.wait_for_timeout(2000)
            
            # فحص الـ 404 الشهير في مكس دروب
            iframe = await page.query_selector(".player--iframe iframe")
            if iframe:
                frame = await iframe.content_frame()
                if frame:
                    content = await frame.evaluate("document.body.innerHTML")
                    if "can't find the" in content and "looking for" in content:
                        log.error("  🚫 رابط Mixdrop ميت!")
                        return None, "mixdrop_dead"
            
            src = await get_iframe_src(page)
            if src: return src, "mixdrop_live"
    return None, None

# --- الدالة الرئيسية (المنسق) ---
async def get_embed_url(page) -> tuple[Optional[str], str]:
    """
    الدالة الرئيسية التي تتحكم في ترتيب الأولويات.
    """
    # 1. حاول أولاً مع MixDrop
    src, status = await extract_mixdrop(page)
    if src:
        log.info(f"✅ تم سحب الرابط بنجاح عبر MixDrop: {src}")
        return src, status

    # 2. إذا فشل MixDrop، حاول مع VidTube
    log.warning("⚠️ فشل MixDrop، جارٍ تجربة VidTube...")
    src, status = await extract_vidtube(page)
    if src:
        log.info(f"✅ تم سحب الرابط بنجاح عبر VidTube: {src}")
        return src, status

    # 3. إذا فشل الجميع
    log.error("❌ لم يتم العثور على أي سيرفر صالح.")
    return None, "none"


def normalize_title(title, for_search=False):
    if not title:
        return ""

    t = str(title).lower()

    # --- الخطوة الناقصة والضرورية ---
    # حذف أي سنة (19xx أو 20xx) قبل أي عملية تنظيف تانية
    t = re.sub(r"\b(19|20)\d{2}\b", " ", t)
    # --------------------------------

    # تنظيف الرموز - لو للبحث بنسيب النقطتين والشرطة والأبوستروف عشان TMDB/IMDB
    # تنظيف الرموز - تم إضافة ' و : للقائمة المسموح بها
    if for_search:
        t = re.sub(r"[^a-zA-Z0-9\u0600-\u06FF\s:\-\']", " ", t)
    else:
        t = re.sub(r"[^a-zA-Z0-9\u0600-\u06FF\s\':]", " ", t)

    stop_words = [
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


async def get_movie_title(page) -> str:
        """يسحب عنوان الفيلم من الصفحة ويقوم بتنظيفه."""
        title_element = await page.query_selector("h1.post-title")
        if title_element:
            raw_title = (await title_element.inner_text()).strip()
        else:
            raw_title = (
                (await page.title()).replace("توب سينما", "").replace("TopCinema", "").strip()
            )

        return normalize_title(raw_title)


async def random_delay():
        t = random.uniform(DELAY_MIN, DELAY_MAX)
        log.info(f"  💤 انتظار {t:.1f} ثانية...")
        await asyncio.sleep(t)

async def get_total_pages(page) -> int:
    """تستخرج رقم آخر صفحة موجودة في الموقع ديناميكياً من أزرار التنقل"""
    try:
        pagination_links = await page.query_selector_all("ul.pagination li a")
        if not pagination_links:
            return 20  # قيمة احتياطية في حال فشل الاستخراج
            
        page_numbers = []
        for link in pagination_links:
            text = (await link.inner_text()).strip()
            if text.isdigit():
                page_numbers.append(int(text))
                
        return max(page_numbers) if page_numbers else 20
    except Exception:
        return 20  # كقيمة أمان لو حدث أي تغيير في تصميم الموقع
# ──────────────────────────────────────────────
# 🚀  Main Runner
# ──────────────────────────────────────────────
async def run_scraper_async():
    sb = get_supabase()
    log.info("✅ تم الاتصال بـ Supabase")

    # 🛡️ صمام الأمان الذكي لمنع تراكم وموت الروابط
    idle_count = get_idle_tasks_count(sb)
    log.info(
        f"🔍 فحص الطابور: يوجد حالياً ({idle_count}) فيلم في حالة idle تنتظر التحميل..."
    )

    if idle_count >= 20:
        log.warning(
            f"🛑 الطابور ممتلئ! (الحد الأقصى المسموح 19 وأنت عندك {idle_count}). تم إيقاف الإسكربر تلقائياً لحماية الروابط من الموت."
        )
        return

    log.info("🚀 الطابور جاهز ومستقر، جاري بدء عملية الصيد والتغذية...")

    total_inserted = 0
    total_skipped = 0
    total_failed = 0

    mixdrop_dead_count = 0
    mixdrop_live_count = 0
    vidtube_saved_count = 0

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=HEADLESS, args=["--no-sandbox", "--disable-setuid-sandbox"])
        
        # 1. تحديد حجم الموقع برمجياً من الصفحة الأولى
        base_page = await browser.new_page(user_agent=random.choice(USER_AGENTS))
        try:
            await base_page.goto(build_page_url(1), wait_until="domcontentloaded", timeout=30_000)
            total_pages = await get_total_pages(base_page)
            log.info(f"📊 [Dynamic Boundary] تم اكتشاف حجم الموقع تلقائياً: إجمالي الصفحات هو {total_pages}")
        except Exception as e:
            total_pages = 50  # قيمة افتراضية واسعة لو فشل الاتصال الأولي
            log.warning(f"⚠️ فشل استخراج حجم الموقع، سيتم اعتماد قيمة افتراضية ({total_pages}): {e}")
        finally:
            await base_page.close()

        # 2. النظام الهجين: اختيار نمط العمل عشوائياً (50% حصري / 50% أرشيف)
        crawl_mode = random.choice(["FRESH_NEW", "ARCHIVE_WASH"])
        
        if crawl_mode == "FRESH_NEW":
            start_dynamic_page = 1
            log.info("🎯 [Hybrid Mode: الحصريات] تقرر البدء من الصفحة (1) لصيد أحدث الأعمال الحالية.")
        else:
            start_dynamic_page = random.randint(2, total_pages)
            log.info(f"🎲 [Hybrid Mode: الأرشيف] تقرر البدء من صفحة عشوائية في العمق: ({start_dynamic_page}) لجرف القديم.")

        # حلقة تكرار تمر من نقطة الانطلاق صعوداً حتى نهاية الموقع
        for page_num in range(start_dynamic_page, total_pages + 1):
            
            # فحص سريع قبل فتح قائمة جديدة: هل امتلأ الطابور أثناء العمل؟
            if get_idle_tasks_count(sb) >= MAX_IDLE_BUFFER:
                log.warning(f"🛑 [Buffer Guard] تم إيقاف السكريبت.. الطابور ممتلئ بـ {MAX_IDLE_BUFFER} روابط فرش تنتظر الوحش.")
                break

            list_url = build_page_url(page_num)
            log.info(f"\n{'═'*55}")
            log.info(f"📄 صفحة القائمة {page_num}: {list_url}")

            # ── افتح صفحة القائمة ──────────────────────────────
            list_page = await browser.new_page(user_agent=random.choice(USER_AGENTS))
            try:
                await list_page.goto(list_url, wait_until="domcontentloaded", timeout=30_000)
                movie_links = await get_movie_links(list_page)
            except Exception as exc:
                log.error(f"❌ فشل تحميل صفحة القائمة: {exc}")
                await list_page.close()
                continue
            finally:
                await list_page.close()

            log.info(f"🎬 وجدت {len(movie_links)} فيلم في الصفحة")

            found_any_new_in_page = False  # فلاج ذكي: هل الصفحة تحتوي على أي عمل جديد؟

            # ── تصفّح كل فيلم داخل الصفحة ───────────────────────────────────
# ── تصفّح كل فيلم داخل الصفحة ───────────────────────────────────
            for idx, movie_url in enumerate(movie_links, 1):
                
                # فحص داخلي سريع قبل الدخول في تفاصيل الفيلم: هل امتلأ الطابور أثناء العمل؟
                if get_idle_tasks_count(sb) >= MAX_IDLE_BUFFER:
                    log.warning(f"🎯 [Buffer Reached] الطابور امتلأ أثناء فحص الأفلام. يكتفي السكريبت بهذا القدر.")
                    break

                log.info(f"\n  [{idx}/{len(movie_links)}] 🎥 {movie_url}")

                try:
                    movie_page = await browser.new_page(user_agent=random.choice(USER_AGENTS))
                    await movie_page.goto(movie_url, wait_until="domcontentloaded", timeout=30_000)
                    
                    movie_title = await get_movie_title(movie_page)
                    watch_url = await get_watch_url(movie_page)
                    await movie_page.close()

                    if not watch_url:
                        log.warning("  ⚠️  لم أجد رابط المشاهدة، تخطي...")
                        total_failed += 1
                        continue

                    # فحص سريع بالاسم في قاعدة البيانات لمنع فتح صفحات المشاهدة الثقيلة للمكرر
                    if already_exists(sb, movie_title, None):
                        log.info(f"  ♻️  الفيلم [{movie_title}] موجود مسبقاً في أرشيفك. تخطي والنزول للتالي في الصفحة...")
                        total_skipped += 1
                        continue  # يكمل الفيلم التالي في الـ 60 عمل دون كسر الصفحة

                    log.info(f"  🔗 صفحة المشاهدة: {watch_url}")

                    # صفحة المشاهدة (تحتاج JavaScript)
                    watch_page = await browser.new_page(user_agent=random.choice(USER_AGENTS))
                    await watch_page.goto(watch_url, wait_until="networkidle", timeout=40_000)
                    embed_url, server_status = await get_embed_url(watch_page)
                    await watch_page.close()

                    if server_status in ["vidtube_fallback", "mixdrop_dead_no_fallback"]:
                        mixdrop_dead_count += 1

                    if not embed_url or embed_url == "404_DELETED":
                        log.warning("  ⚠️  لم أجد رابط الإيمباد أو الرابط ميت، تخطي...")
                        total_failed += 1
                        continue

                    # تأكيد أخير برابط الإيمباد
                    if already_exists(sb, movie_title, embed_url):
                        log.info("  ♻️  الرابط موجود مسبقاً، تخطي...")
                        total_skipped += 1
                        continue

                    # إذا وصلنا هنا فالعمل جديد تماماً وفرش
                    found_any_new_in_page = True
                    
                    ok = insert_task(sb, movie_title, embed_url)
                    if ok:
                        log.info("  ✅ تم الإدراج بنجاح بالتنقيط!")
                        total_inserted += 1
                        if server_status == "mixdrop_live":
                            mixdrop_live_count += 1
                        elif server_status == "vidtube_fallback":
                            vidtube_saved_count += 1
                            
                        # فحص الطابور فوراً بعد الإدراج الناجح لضبط سرعة التغذية
                        if get_idle_tasks_count(sb) >= MAX_IDLE_BUFFER:
                            log.warning(f"🎯 [Buffer Reached] الطابور يحتوي الآن على ({MAX_IDLE_BUFFER}) مهام جاهزة. يكتفي السكريبت بهذا القدر.")
                            break
                    else:
                        total_failed += 1

                except PlaywrightTimeout:
                    log.error("  ⏱️  انتهت المهلة، تخطي هذا الفيلم...")
                    total_failed += 1
                except Exception as exc:
                    log.error(f"  ❌ خطأ غير متوقع: {exc}")
                    total_failed += 1
                finally:
                    if 'movie_page' in locals():
                        try: await movie_page.close()
                        except: pass
                    if 'watch_page' in locals():
                        try: await watch_page.close()
                        except: pass

                await asyncio.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

            # ── استراتيجيات الخروج والتحكم الذكي بعد نهاية فحص الصفحة بالكامل ──
            current_idle = get_idle_tasks_count(sb)
            if current_idle >= MAX_IDLE_BUFFER:
                log.info("🛑 تم إنهاء الجولة بنجاح للوصول للحد الأقصى المطلوب في الطابور.")
                break

            # في نمط الحصريات: لو الصفحة 1 مكررة بالكامل، اقفل فوراً لأن ما بعدها مكرر بالتأكيد
            if crawl_mode == "FRESH_NEW" and not found_any_new_in_page:
                log.warning("⚠️ [Stop Strategy] نمط الحصريات: الصفحة 1 مكررة بالكامل. تم إنهاء الجولة لتوفير الموارد.")
                break
                
            # في نمط الأرشيف: لو الصفحة مكررة بالكامل، لا تقفل السكريبت! بل دع الحلقة تنتقل تلقائياً للصفحة التالية صعوداً
            if crawl_mode == "ARCHIVE_WASH" and not found_any_new_in_page:
                log.warning(f"🔄 [Archive Wash] الصفحة {page_num} مغسولة بالكامل مسبقاً. نرفض الاستسلام، تلقائياً للانتقال للصفحة التالية صعوداً...")

            await asyncio.sleep(random.uniform(DELAY_MIN, DELAY_MAX))  # تأخير إضافي آمن بين صفحات القوائم

        await browser.close()

    # ── ملخص نهائي ─────────────────────────────────────────
    log.info(f"\n{'═'*55}")
    log.info("📊 ملخص العملية التفصيلي:")
    log.info(f"   ✅ إجمالي المدرج في الـ DB:      {total_inserted}")
    log.info(f"   ♻️  أعمال مكررة تم تخطيها:      {total_skipped}")
    log.info(f"   ❌ إجمالي الفشل والأخطاء:         {total_failed}")
    log.info(f"{'─'*55}")
    log.info(f"   💀 روابط Mixdrop البايظة المكتشفة: {mixdrop_dead_count}")
    log.info(f"   🍏 روابط Mixdrop السليمة المسحوبة: {mixdrop_live_count}")
    log.info(f"   📺 روابط VidTube (متعدد) المُنقذة:  {vidtube_saved_count}")
    log.info(f"{'═'*55}")
    