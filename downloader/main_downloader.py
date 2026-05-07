import os
import time
import re
import shutil
import nest_asyncio
from urllib.parse import unquote
import asyncio
import arabic_reshaper
from bidi.algorithm import get_display
import subprocess
from internetarchive import upload as archive_upload
from urllib.parse import urlparse

try:
    from .logger_setup import get_beast_logger
except ImportError:
    import sys
    import os

    sys.path.append(os.path.dirname(__file__))
    from logger_setup import get_beast_logger
# استدعاء اللوجر باسم المشروع
from .processors import (
    tqdm,
    normalize_title,
    get_clean_media_data,
    get_movie_data,
    upload_to_doodstream,
    upload_to_streamtape,
    upload_to_mixdrop,
    upload_to_voe_api,
    upload_to_vk_local,
    upload_to_lulustream,
    upload_poster_to_cloudinary,
)

# 2. استيراد المحرك
from .engine import *
from .engine import (
    upload_to_telegram_only,
    ensure_dependencies,
    ProgressStream,
    send_to_telegram,
)

log = get_beast_logger("GuardianUltra")

# 3. تنظيف استيراد سوبابيز
try:
    from supabase import create_client, Client as SupabaseClient
except ImportError:
    log.error("❌ خطأ: مكتبة supabase غير مثبتة.")

# تفعيل nest_asyncio
nest_asyncio.apply()

# تثبيت بيئة tqdm عالمياً داخل هذا الملف أيضاً
os.environ["TQDM_MININTERVAL"] = "2.0"

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: SupabaseClient = create_client(SUPABASE_URL, SUPABASE_KEY)


# استدعاء المفاتيح من البيئة بدلاً من كتابتها يدوياً
# أرشيف الإنترنت (Internet Archive) credentials
ARCHIVE_ACCESS_KEY = os.getenv("ARCHIVE_ACCESS_KEY")
ARCHIVE_SECRET_KEY = os.getenv("ARCHIVE_SECRET_KEY")
# Lulustream credentials
lu_key = os.getenv("LULUSTREAM_API_KEY")
# Doodstream credentials
dood_api_key = os.getenv("DOOD_API_KEY")
# Streamtape credentials
st_login = os.getenv("STREAMTAPE_LOGIN")
st_key = os.getenv("STREAMTAPE_KEY")
mix_user = os.getenv("MIXDROP_EMAIL")
mix_key = os.getenv("MIXDROP_API_KEY")


def save_to_supabase(
    current_voe,
    current_down,
    current_vk,
    display_title,
    original_task_name,
    meta_story,
    final_poster,  # أضفهم هنا كمعاملات عادية
    meta_year,
    meta_rating,
    identifier,
    archive_url,
    meta_data=None,
    tmdb_id=None,
    labels=None,
    runtime=None,
    duration_iso=None,
):
    try:

        # نستخدم الاسم النظيف لاستخراج العنوان والنوع ورقم الموسم والحلقة
        c_title, c_cat, extracted_season_no, actual_ep_no = get_clean_media_data(
            display_title
        )

        # توليد slug تلقائي للميديا
        # إذا كان الاسم إنجليزي، نستخدم الحروف الإنجليزية، وإذا كان عربي نستخدم العربي
        generated_slug = c_title.lower().strip().replace(" ", "-")
        # تنظيف الـ slug من الرموز الغريبة مع الحفاظ على الحروف العربية والإنجليزية والأرقام والشرطة
        generated_slug = re.sub(r"[^a-z0-9\u0600-\u06FF-]", "", generated_slug)
        # إزالة الشرطات المتكررة
        generated_slug = re.sub(r"-+", "-", generated_slug).strip("-")

        # --- [تعديل 1]: تحديد الميديا تايب بدقة (movie / series) ---
        # الـ category بتفضل movie/tv عشان السيستم القديم، بس الـ media_type بيبقى موفي/سيريس
        m_type = "movie" if c_cat == "movie" else "series"

        # --- [تعديل 2]: حماية التايتل (لو التاسك فيه اسم يدوي نستخدمه) ---
        # بنشيك هل original_task_name رابط؟ لو مش رابط يبقى هو الأولوية
        if original_task_name and not original_task_name.startswith(
            ("http://", "https://")
        ):
            final_title = original_task_name
        else:
            final_title = c_title  # الاسم اللي السكربت نظفه أو جابه من TMDB

        media_payload = {
            "tmdb_id": str(tmdb_id) if tmdb_id else None,
            "title": final_title,  # العنوان المحمي
            "story": meta_story,
            "poster_url": final_poster,
            "category": c_cat,  # movie or tv (للسيستم)
            "media_type": m_type,  # movie or series (للموقع)
            "slug": generated_slug,
            "year": str(meta_year),
            "rating": str(meta_rating),
            "labels": labels,
            "runtime": runtime,
            "duration_iso": duration_iso,
        }
        # تنظيف ذكي: يحذف القيمة لو كانت None أو نص بيدل على الفشل أو رابط Placeholder
        useless_values = [
            None,
            "",
            "لا يوجد وصف",
            "جاري تحديث القصة...",
            "N/A",
            "غير محدد",
        ]

        media_payload = {
            k: v
            for k, v in media_payload.items()
            if v not in useless_values and "via.placeholder.com" not in str(v)
        }
        # 1. ابحث عن المسلسل أولاً لمنع دهس البيانات (القصة والبوستر)
        # --- بداية الجزء المحصن ضد أخطاء 502 ---
        m_id = None
        e_id = None
        for attempt in range(3):
            try:
                # 1. البحث عن أو إنشاء الميديا (Media)
                existing_media = (
                    supabase.table("medias")
                    .select("id")
                    .eq("title", c_title)
                    .eq("year", str(meta_year))
                    .execute()
                )

                # --- التعديل النهائي والذكي جداً بعد تفعيل Unique في سوبابيز ---
                # 1. البحث عن الميديا (بالـ ID أولاً ثم بالاسم المنظف) لضمان عدم التكرار
                m_id = None
                query = None

                # محاولة البحث بالـ ID لو متوفر
                if tmdb_id:
                    query = (
                        supabase.table("medias")
                        .select("*")
                        .eq("tmdb_id", str(tmdb_id))
                        .execute()
                    )

                # لو مفيش ID أو منفعش، نبحث بالاسم الذكي
                if not query or not query.data:
                    # الخطوة 1: البحث المطابق المباشر
                    query = (
                        supabase.table("medias")
                        .select("*")
                        .eq("title", c_title)
                        .eq("year", str(meta_year))
                        .execute()
                    )

                    # الخطوة 2: لو لسه مش موجود، نجرب البحث بـ "like" للكلمات الأساسية
                    if not query.data:
                        # نجلب كل الأعمال اللي فيها جزء من الاسم ونفلترها برمجياً
                        # ده حل "ذكي" للأعمال العربية اللي مش في TMDB
                        search_results = (
                            supabase.table("medias")
                            .select("*")
                            .ilike("title", f"%{c_title}%")
                            .execute()
                        )
                        for row in search_results.data:
                            if normalize_title(row["title"]) == c_title:
                                query = search_results
                                query.data = [row]  # نكتفي بهذا السجل
                                break

                if query and query.data:
                    m_id = query.data[0]["id"]

                    # --- التعديل: قراءة البيانات "لحساب" المتغيرات وليس للتعديل ---
                    # بنسحب القصة والبوستر من سوبابيز عشان نستخدمهم في تليجرام صح
                    existing_data = query.data[0]

                    if existing_data.get("story"):
                        meta_story = existing_data["story"]
                    if existing_data.get("poster_url"):
                        final_poster = existing_data["poster_url"]

                    log.info(
                        f"🛡️ [حماية]: تم العثور على '{c_title}' (ID: {m_id})، تم سحب البيانات للأرشفة دون تعديل."
                    )
                else:
                    # استخدام upsert لضمان أنه في حالة "السباق اللحظي" لا يحدث خطأ 23505
                    log.info(f"🆕 [إنشاء]: سجل جديد لـ '{c_title}'...")
                    new_media = (
                        supabase.table("medias")
                        .upsert(media_payload, on_conflict="title, year")
                        .execute()
                    )
                    if new_media.data:
                        m_id = new_media.data[0]["id"]

                # --- [تعديل جوهري]: تحديث الـ slug ليبدأ بـ ID الميديا لضمان توافق Next.js ---
                if m_id:
                    # نستخدم الـ generated_slug الأصلي ونضيف له الـ ID
                    # نتأكد أولاً أن الـ slug الحالي لا يبدأ بالفعل بالـ ID الصحيح
                    check_res = (
                        supabase.table("medias").select("slug").eq("id", m_id).execute()
                    )
                    if check_res.data:
                        current_db_slug = check_res.data[0]["slug"]
                        target_slug = f"{m_id}-{generated_slug}"

                        if current_db_slug != target_slug:
                            log.info(f"🔗 تحديث الرابط (Slug) إلى: {target_slug}")
                            supabase.table("medias").update({"slug": target_slug}).eq(
                                "id", m_id
                            ).execute()
                            generated_slug = target_slug
                        else:
                            generated_slug = current_db_slug

                break  # إذا وصلنا هنا بنجاح، نخرج من حلقة المحاولات
            except Exception as e:
                if attempt < 2:
                    log.warning(
                        f"⚠️ سوبابيز متعثر في مرحلة التعريف (502)، محاولة {attempt+1}..."
                    )
                    time.sleep(3)
                else:
                    raise e  # لو فشل تماماً بعد 3 مرات يرمي الخطأ للـ Except الكبيرة
        # --- نهاية الجزء المحصن ---

        # --- [تعديل جوهري]: إنشاء أو تحديث الموسم (Season) أولاً للمسلسلات ---
        s_id = None
        if c_cat == "tv":
            # استخدام رقم الموسم المستخرج بدلاً من الهاردكود
            season_number = extracted_season_no if extracted_season_no else 1
            season_slug = f"{generated_slug}-season-{season_number}"
            log.info(f"📡 جاري معالجة الموسم رقم {season_number} للميديا {m_id}...")
            try:
                # البحث عن الموسم أو إنشاؤه
                existing_season = (
                    supabase.table("seasons")
                    .select("id")
                    .eq("media_id", m_id)
                    .eq("season_number", season_number)
                    .execute()
                )
                if existing_season.data:
                    s_id = existing_season.data[0]["id"]
                    log.info(f"✅ تم العثور على الموسم في القاعدة بـ ID: {s_id}")
                else:
                    log.info(f"🆕 الموسم {season_number} غير موجود، جاري إنشاؤه...")
                    new_season = (
                        supabase.table("seasons")
                        .insert(
                            {
                                "media_id": m_id,
                                "season_number": season_number,
                                "slug": season_slug,
                            }
                        )
                        .execute()
                    )
                    if new_season.data:
                        s_id = new_season.data[0]["id"]
                        log.info(f"✅ تم إنشاء موسم جديد بـ ID: {s_id}")
            except Exception as se:
                log.warning(f"⚠️ خطأ في إنشاء الموسم: {se}")

        # --- [تعديل جوهري]: إنشاء أو تحديث الحلقة (Episode) قبل الروابط ---
        actual_ep_no = actual_ep_no if actual_ep_no else 1
        ep_slug = f"{generated_slug}-episode-{actual_ep_no}"

        episode_payload = {
            "media_id": m_id,
            "season_id": s_id,  # ربط الحلقة بالموسم
            "episode_number": actual_ep_no,
            "slug": ep_slug,  # إضافة slug للحلقة
            "identifier": identifier,
            "status_message": "Waiting...",
            "progress_percent": 0,
        }

        # البحث عن الحلقة لإنشائها أو تحديث الـ identifier الخاص بها
        existing_ep = (
            supabase.table("episodes")
            .select("id")
            .eq("media_id", m_id)
            .eq("episode_number", actual_ep_no)
            .execute()
        )

        if existing_ep.data:
            e_id = existing_ep.data[0]["id"]
            supabase.table("episodes").update(
                {"identifier": identifier, "season_id": s_id, "slug": ep_slug}
            ).eq("id", e_id).execute()
        else:
            new_ep = supabase.table("episodes").insert(episode_payload).execute()
            if new_ep.data:
                e_id = new_ep.data[0]["id"]

        # --- [تعديل]: التعامل مع التصنيفات (Genres) تلقائياً ---
        if labels and m_id:
            genre_list = [g.strip() for g in labels.split(",") if g.strip()]
            for g_name in genre_list:
                try:
                    g_slug = g_name.lower().replace(" ", "-")
                    # 1. البحث عن التصنيف أو إنشاؤه
                    genre_res = (
                        supabase.table("genres")
                        .select("id")
                        .eq("name", g_name)
                        .execute()
                    )
                    g_id = None
                    if genre_res.data:
                        g_id = genre_res.data[0]["id"]
                    else:
                        new_g = (
                            supabase.table("genres")
                            .insert({"name": g_name, "slug": g_slug})
                            .execute()
                        )
                        if new_g.data:
                            g_id = new_g.data[0]["id"]

                    # 2. ربط التصنيف بالميديا في جدول media_genres
                    if g_id:
                        supabase.table("media_genres").upsert(
                            {"media_id": m_id, "genre_id": g_id},
                            on_conflict="media_id, genre_id",
                        ).execute()
                except Exception as ge:
                    log.warning(f"⚠️ خطأ في معالجة التصنيف {g_name}: {ge}")

        # 1. بناء القائمة الآن بعد التأكد من وجود e_id
        link_entries = []
        if e_id:  # تأكد أن الـ ID موجود
            if current_voe and current_voe not in ["Failed", "Pending"]:
                link_entries.append(
                    {"episode_id": e_id, "server_name": "voe", "url": current_voe}
                )
            if current_vk and current_vk not in ["Failed", "Pending"]:
                link_entries.append(
                    {"episode_id": e_id, "server_name": "vk", "url": current_vk}
                )
            if archive_url and "Failed" not in archive_url and archive_url != "Pending":
                link_entries.append(
                    {"episode_id": e_id, "server_name": "archive", "url": archive_url}
                )
            if current_down and current_down != "Failed":
                link_entries.append(
                    {"episode_id": e_id, "server_name": "download", "url": current_down}
                )

        # 2. الآن نقوم بتحديث السيرفرات الموجودة فقط (تنفيذ الـ upsert لكل رابط في القائمة)
        # 2. الآن نقوم بتحديث السيرفرات الموجودة فقط مع آلية إعادة المحاولة (Retry)
        for entry in link_entries:
            for attempt in range(3):  # حاول 3 مرات كحد أقصى
                try:
                    supabase.table("links").upsert(
                        entry, on_conflict="episode_id, server_name"
                    ).execute()
                    break  # نجح الأمر، اخرج من حلقة المحاولات لهذا الرابط
                except Exception as link_err:
                    if attempt < 2:
                        log.warning(
                            f"⚠️ سوبابيز مشغول (502/Timeout)، محاولة رقم {attempt+1} خلال 3 ثوانٍ..."
                        )
                        time.sleep(3)
                    else:
                        log.error(
                            f"❌ فشل تسجيل رابط {entry['server_name']} بعد 3 محاولات: {link_err}"
                        )
        return e_id, m_id, meta_story, final_poster
    except Exception as e:
        log.error(f"❌ خطأ أثناء الحفظ في ساب باز: {e}")
        return None, None, meta_story, final_poster


# قائمة "الخداع" للمواقع المختلفة - ضعها في أعلى الملف
SITES_COOKBOOK = {
    "vod3": {
        "Referer": "https://vod3.cf.dmcdn.net/",
        "Origin": "https://vod3.cf.dmcdn.net/",
    },
    "topcinema": {
        "Referer": "https://topcinema.rip/",
        "Origin": "https://topcinema.rip",
    },
    "vidtube": {
        "Referer": "https://vidtube.one/",
        "Origin": "https://vidtube.one",
    },
    "vidsrc": {
        "Referer": "https://vidsrc.me/",
        "Origin": "https://vidsrc.me",
    },
    "upbam": {
        "Referer": "https://upbam.org/",
        "Origin": "https://upbam.org",
    },
    "cdn-tube": {
        "Referer": "https://vidtube.one/",
        "Origin": "https://vidtube.one",
    },
    "dailymotion": {
        "Referer": "https://www.dailymotion.com/",
        "Origin": "https://www.dailymotion.com/",
    },
    "vk": {
        "Referer": "https://vk.com/",
        "Origin": "https://vk.com/",
    },
    "vkvideo": {
        "Referer": "https://vkvideo.ru/",
        "Origin": "https://vkvideo.ru/",
    },
    "voe": {
        "Referer": "https://voe.sx/",
        "Origin": "https://voe.sx/",
    },
    "archive": {
        "Referer": "https://archive.org/",
        "Origin": "https://archive.org/",
    },
    "myvidplay": {
        "Referer": "https://myvidplay.com/",
        "Origin": "https://myvidplay.com/",
    },
    "lulustream": {
        "Referer": "https://topcinemaa.com/",  # الخداع بأننا جايين من موقع الأفلام
        "Origin": "https://topcinemaa.com",
    },
    "luluvdo": {
        "Referer": "https://topcinemaa.com/",
        "Origin": "https://topcinemaa.com",
    },
    "mixdrop": {
        "Referer": "https://mixdrop.top/",
        "Origin": "https://mixdrop.top/",
    },
    "streamtape": {
        "Referer": "https://streamtape.com/",
        "Origin": "https://streamtape.com/",
    },
    "telegram_direct": {
        "Referer": "https://eslam315-egy-streamer.hf.space/",
        "Origin": "https://eslam315-egy-streamer.hf.space/",
    },
    "huggingface": {
        "Referer": "https://huggingface.co/",
        "Origin": "https://huggingface.co/",
    },
    "ok": {
        "Referer": "https://ok.ru",
        "Origin": "https://ok.ru",
    },
    "telecima": {
        "Referer": "https://telecima.sbs/",
        "Origin": "https://telecima.sbs/",
    },
    "cimafree": {
        "Referer": "https://cimafree.onl/",
        "Origin": "https://cimafree.onl/",
    },
    "topcinemaa": {
        "Referer": "https://topcinemaa.com/",
        "Origin": "https://topcinemaa.com/",
    },
    "geo.dailymotion": {
        "Referer": "https://geo.dailymotion.com/",
        "Origin": "https://geo.dailymotion.com/",
    },
    "goodstream": {
        "Referer": "https://goodstream.one/",
        "Origin": "https://goodstream.one",
    },
}


def get_smart_headers(url):
    headers = []
    # الهيدر الافتراضي في حال لم يكن الموقع في القائمة
    found = False
    for site, config in SITES_COOKBOOK.items():
        if site in url:
            for key, value in config.items():
                headers.extend(["--add-header", f"{key}: {value}"])
            found = True
            break

    # إذا لم يجد الموقع، يستخدم هيدر عام لتقليل خطر الحظر
    if not found:
        headers.extend(["--add-header", f"Referer: {url}"])
    return headers


# --- 1. إضافة دالة الصيد في أعلى ملف سكربت التحميل ---
async def get_direct_link_via_playwright(embed_url):

    from playwright.async_api import async_playwright

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


async def get_mixdrop_direct_link(embed_url):
    from playwright.async_api import async_playwright

    target_url = embed_url.replace("/e/", "/f/")
    if "?download" not in target_url:
        target_url += "?download"

    log.info(f"🕵️ محاكاة سلوك بشري على: {target_url}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True
        )  # يمكن جعلها False لو بتجرب محلياً
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        try:
            await page.goto(target_url, wait_until="domcontentloaded")
            btn_selector = "a.download-btn"

            # رفعنا المدى لـ 10 لضمان وجود محاولات كافية بعد الـ Reload
            for i in range(1, 11):
                try:
                    await page.wait_for_selector(
                        btn_selector, state="visible", timeout=10000
                    )
                    log.info(f"🖱️ نقرة رقم {i}...")

                    # --- ⚡ تعديل الـ Reload الذكي ⚡ ---
                    if i == 5:
                        log.info(
                            "🔄 الموقع يبدو متجمداً.. جاري إعادة تحميل الصفحة (Reload) للتنشيط..."
                        )
                        await page.reload(wait_until="domcontentloaded")
                        await page.wait_for_timeout(3000)
                        continue
                    # ----------------------------------

                    try:
                        async with context.expect_page(timeout=10000) as new_page_info:
                            await page.click(btn_selector)

                        ad_page = await new_page_info.value
                        log.info(f"📺 إعلان ظهر، ننتظره قليلاً...")
                        await page.wait_for_timeout(5000)
                        await ad_page.close()
                    except Exception:
                        log.warning(f"⚠️ النقرة {i} لم تفتح إعلاناً.")
                    # ----------------------------------

                    await page.bring_to_front()

                    # فحص الرابط المباشر - صيد الدومينات الفرعية الجديدة
                    href = await page.get_attribute(btn_selector, "href")

                    if href and href.startswith("http"):
                        # فحص ذكي: هل الرابط يحتوي على كلمة mxcontent (بأي شكل) أو ليس له علاقة بـ mixdrop؟
                        is_valid_direct = "mxcontent" in href or (
                            not ("?download" in href or "mixdrop" in href)
                        )

                        if is_valid_direct:
                            log.info(f"✅ تم صيد الرابط بنجاح: {href[:60]}...")

                            await browser.close()
                            return href

                    log.info("⏳ الرابط لم يظهر بعد، ننتظر ثواني للنقرة التالية...")
                    await page.wait_for_timeout(
                        5000
                    )  # زودنا الانتظار لـ 5 ثواني عشان ندي فرصة للسيرفر
                except Exception as e:
                    log.warning(f"⚠️ خطأ في المحاولة {i}: {str(e)}")
                    continue  # لو محاولة فشلت يكمل للي بعدها ميفصلش السكريبت

            await browser.close()
            return None

        except Exception as e:
            log.error(f"❌ خطأ أثناء المحاكاة البشرية: {str(e)}")
            await browser.close()
            return None


async def pyramid_ultimate_beast(url, name, task_id=None, meta_data=None):
    # 1. تحديد المسار باحترافية (كشف التزييف)
    try:
        import google.colab  # هذا السطر يجب أن يكون داخل الـ try

        BASE_PATH = "/content"
    except ImportError:
        # إذا فشل الاستيراد، فهذا يعني أننا لسنا في كولاب
        BASE_PATH = (
            "/kaggle/working" if os.path.exists("/kaggle/working") else os.getcwd()
        )

    BASE_DIR = os.path.join(BASE_PATH, "project")

    # 2. التأكد من إنشاء المجلد والدخول إليه
    os.makedirs(BASE_DIR, exist_ok=True)
    os.chdir(BASE_DIR)

    # --- 🟢 تجهيز اللوجو (مرة واحدة لكل عملية) ---
    # مجلد خاص للأدوات الثابتة (اللوجو) بعيد عن مجلد العمليات
    TOOLS_DIR = os.path.join(BASE_PATH, "tools")
    os.makedirs(TOOLS_DIR, exist_ok=True)

    LOGO_URL = "https://res.cloudinary.com/dbahqgo8j/image/upload/q_auto,f_auto,w_80,h_80,c_fill,r_max/blogger/logo.webp"
    LOGO_FILE = os.path.join(TOOLS_DIR, "watermark.webp")  # تغيير المسار لـ TOOLS_DIR

    if not os.path.exists(LOGO_FILE):
        try:
            import httpx

            with httpx.Client(follow_redirects=True) as client:
                resp = client.get(LOGO_URL)
                with open(LOGO_FILE, "wb") as f:
                    f.write(resp.content)
            log.info("✅ اللوجو جاهز ومؤمن في مجلد الأدوات.")
        except:
            pass
    # هذا السطر سيطبع الآن المسار الحقيقي الصحيح (/content/project في كولاب)
    log.info(f"🛠️ مسار العمل الحالي للوحش: {os.getcwd()}")
    # باقي الكود كما هو...

    await ensure_dependencies()
    timestamp = int(time.time())

    # --- 1. تنظيف الاسم وجلب البيانات الذكية ---

    if "topcinema.rip" in str(name):
        decoded = unquote(str(name))
        match = re.search(r"فيلم-(.*?)-مترجم", decoded)
        name = (
            match.group(1).replace("-", " ").title()
            if match
            else decoded.split("/")[-2].replace("-", " ").replace("فيلم", "").title()
        )

    log.info(f"🔍 جلب بيانات العمل من TMDB/IMDB للتحقق من الأرشيف...")
    # احتفظ بالاسم الأصلي الذي كتبته في التاسك كخطة احتياطية
    original_task_name = str(name).strip()

    # استخراج الاسم النظيف للبحث في TMDB (بدلاً من البحث بالاسم الكامل مع رقم الحلقة)
    # التعديل: إذا كان المدخل رابطاً، نمرره كما هو لـ get_movie_data ليتعامل معه
    # 1. استخراج السنة من الاسم الأصلي (Task Name) لاستخدامها في البحث الدقيق
    year_match = re.search(r"\b((?:19|20)\d{2})\b", original_task_name)
    extracted_year = year_match.group(1) if year_match else None

    if "http" in original_task_name or original_task_name.startswith(("tt", "tmdb")):
        search_query_clean = original_task_name
    else:
        # هنا get_clean_media_data ترجع الاسم بدون سنة
        search_query_clean, _, _, _ = get_clean_media_data(original_task_name)

    log.info(
        f"🔎 البحث عن: {search_query_clean} "
        + (f"({extracted_year})" if extracted_year else "")
        + " ..."
    )

    # 2. تعديل استدعاء get_movie_data ليدعم السنة (إذا كانت الدالة تدعم ذلك)
    # ملاحظة: سنمرر السنة للدالة لضمان دقة البحث
    (
        tmdb_id_fetched,
        display_title_tmdb,
        meta_story,
        final_poster,
        meta_labels,
        meta_duration,
        meta_rating,
        meta_runtime,
        meta_year,
    ) = get_movie_data(
        search_query_clean if search_query_clean else name, year=extracted_year
    )

    # دمج الاسم المجلوب مع تفاصيل الحلقة من التاسك الأصلي
    display_title = display_title_tmdb if display_title_tmdb else original_task_name

    # التأكد من بقاء معلومات الموسم والحلقة في العنوان المعروض
    if "الموسم" in original_task_name and "الموسم" not in display_title:
        display_title = f"{display_title} {re.search(r'(الموسم\s*\d+)', original_task_name).group(1)}"
    if "الحلقة" in original_task_name and "الحلقة" not in display_title:
        # استخراج "الحلقة X" وإضافتها
        ep_match = re.search(r"(الحلقة\s*\d+|ح\s*\d+)", original_task_name)
        if ep_match:
            display_title = f"{display_title} {ep_match.group(1)}"

    # --- 2. نظام منع التكرار الاحترافي (Supabase) ---
    # 1. استخراج البيانات النظيفة فوراً قبل أي فحص
    clean_title_search, category_search, current_season_no, current_ep_no = (
        get_clean_media_data(display_title)
    )
    # البحث الذكي عن الميديا (بالاسم المطابق أو المنظف)
    try:
        media_id = None
        # الخطوة 1: البحث المباشر
        m_query = (
            supabase.table("medias")
            .select("id, title")
            .eq("title", clean_title_search)
            .eq("year", meta_year)
            .execute()
        )

        if m_query.data:
            media_id = m_query.data[0]["id"]
        else:
            # الخطوة 2: البحث الذكي بالاسم المنظف (للمحتوى العربي غير المسجل في TMDB)
            search_results = (
                supabase.table("medias")
                .select("id, title")
                .ilike("title", f"%{clean_title_search}%")
                .execute()
            )
            for row in search_results.data:
                if normalize_title(row["title"]) == clean_title_search:
                    media_id = row["id"]
                    break

        if media_id:
            if category_search == "movie":
                # للأفلام: لو الميديا موجودة ولها حلقات (فيلم واحد)، إذن مكرر
                ep_query = (
                    supabase.table("episodes")
                    .select("id")
                    .eq("media_id", media_id)
                    .execute()
                )
                if ep_query.data:
                    log.info(f"✅ [تخطي]: الفيلم '{display_title}' موجود بالفعل!")
                    return
            # للمسلسلات: لا يمكننا الفحص هنا لأننا لا نعرف الحلقات الموجودة في الرابط بعد
            # سيتم الفحص داخل لووب الحلقات لاحقاً
    except Exception as e:
        log.warning(f"⚠️ فشل فحص التكرار الأولي: {e}")

    # --- 3. حجز مكان أولي (للمسلسلات سيتم تحديثه لاحقاً لكل حلقة) ---
    # إنشاء identifier مؤقت للتحميل
    temp_id = f"loading_{timestamp}"

    # استدعاء الحفظ الأولي للحصول على e_id
    # التعديل: استلام 4 قيم بدلاً من 3
    e_id, media_id, meta_story, final_poster = save_to_supabase(
        None,
        None,
        "Pending",
        display_title,
        original_task_name,
        meta_story,
        final_poster,
        meta_year,
        meta_rating,
        temp_id,
        "Pending",
        tmdb_id=tmdb_id_fetched,
        labels=meta_labels,
        runtime=meta_runtime,
        duration_iso=meta_duration,
    )

    if not e_id:
        log.warning("⚠️ فشل الحصول على ID من ساب باز، لن نتمكن من عرض التقدم الحي.")

    # --- 3. استكمال العمل في حال كان الفيلم جديداً ---
    clean_name = (
        "".join([c for c in display_title if c.isalnum() or c in (" ", ".", "_")])
        .strip()
        .replace(" ", "_")
    )

    # --- 🟢 التعديل الجوهري الموحد (امسح أي تكرار قبله أو بعده) ---
    is_local_file = os.path.exists(url)
    actual_downloaded_path = None
    timestamp = int(time.time())

    if is_local_file:
        log.info(f"♻️ اكتشاف ملف محلي: {url} - سيتم تخطي التحميل.")
        actual_downloaded_path = url
    else:
        log.info(f"📡 رابط ويب، جاري التجهيز للسحب...")

    # إنشاء مجلد العمل
    extract_dir = os.path.join(BASE_DIR, f"extracted_{timestamp}")
    os.makedirs(extract_dir, exist_ok=True)

    # تعريف قالب التحميل
    download_path_template = os.path.join(extract_dir, f"down_{timestamp}.%(ext)s")
    # --------------------------------------------------------

    log.info(f"📡 جاري فحص الرابط وبدء السحب...")

    # ══════════════════════════════════════════════════════════════
    # فحص مبكر للرابط مع نظام المحاولات المتكررة (Retries)
    # ══════════════════════════════════════════════════════════════
    # ══════════════════════════════════════════════════════════════
    # بدء عملية التحميل مباشرة (بدون فحص مبكر)
    # ══════════════════════════════════════════════════════════════
    if not is_local_file:
        log.info(f"   🚀 [Direct Start] الرابط معتمد — جاري التحميل فوراً...")

    # هنا ييجي كود الـ yt-dlp بتاعك مباشرة

    # 1. جلب الهيدرز الذكية بناءً على الرابط الممرر للدالة
    # --- 2. دمج المنطق داخل دالة التحميل الأساسية ---

    # 1. معالجة روابط VidTube/Lulu
    if "vidtube.one" in url or "cdn-tube" in url:
        log.info("🎯 تم اكتشاف رابط VidTube/Lulu.. جاري استخراج الرابط المباشر...")
        direct_link = await get_direct_link_via_playwright(url)
        if direct_link:
            log.info(f"✅ تم صيد الرابط بنجاح! سيتم التحميل الآن.")
            url = direct_link
        else:
            log.warning("⚠️ فشل الصيد، سنحاول بالرابط الأصلي (قد يفشل).")

    # 2. معالجة روابط MixDrop (باستخدام elif لزيادة الكفاءة)
    elif "mixdrop" in url:
        log.info("🎯 تم اكتشاف رابط MixDrop.. جاري الصيد من صفحة التحميل...")
        direct_link = await get_mixdrop_direct_link(url)
        if direct_link:
            log.info(f"✅ تم صيد رابط MixDrop المباشر بنجاح.")
            url = direct_link
        else:
            log.warning("⚠️ فشل الصيد، سنحاول بالرابط الأصلي (قد يفشل).")

    # الآن يكمل الكود بناء الـ cmd بالرابط الجديد (url)
    smart_headers = get_smart_headers(url)
    # ... باقي كود بناء الـ cmd اللي عندك ...

    # 2. بناء أمر الوحش الموحد لضمان تجاوز الحماية في كل الحالات
    cmd = [
        "yt-dlp",
        "--impersonate",
        "chrome",  # تفعيل محاكاة المتصفح باستخدام curl_cffi
        "-v",
        "--no-playlist",
        "--geo-bypass",  # محاولة تخطي الحظر الجغرافي
        "--user-agent",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "--add-header",
        "Accept: video/webp,video/apng,video/*,*/*;q=0.8",
        "--add-header",
        "Accept-Language: en-US,en;q=0.9,ar;q=0.8",
        "--no-check-certificate",
        "--retries",
        "infinite",
        "--socket-timeout",
        "120",
        "--concurrent-fragments",
        "10",
        "--file-access-retries",
        "infinite",
        "--fragment-retries",
        "infinite",
        "--hls-use-mpegts",
    ]
    # دمج هيدرز الخداع من الـ Cookbook
    cmd.extend(smart_headers)
    # --- المكاااااان الصحيح للكود الجديد هنا ---
    if "lulu" in url:
        # بنجبره يستخدم الـ Referer بتاع موقع الأفلام عشان يفتح السيرفر
        cmd.extend(["--referer", "https://topcinemaa.com/"])
        # ملاحظة: شيل سطر الـ cookies لو شغال على Colab لأنه مش هيلاقي كروم هناك
    # ------------------------------------------
    # دعم إضافي لسيرفرات vidtube و cdn-tube
    if "vidtube" in url or "cdn-tube" in url:
        cmd.extend(["--extractor-args", "jwplayer:base-url=https://vidtube.one/"])
    cmd.extend(
        [
            "-f",
            # الشرط الجديد: ابحث عن أي جودة يكون البُعد الأصغر فيها (width أو height) لا يتعدى 720 أو 1080
            "(bestvideo[width<=720][height<=1280]/bestvideo[height<=720][width<=1280]+bestaudio/best[width<=720][height<=1280]/best[height<=720][width<=1280]) / "
            "(bestvideo[width<=1080][height<=1920][filesize<1950M]+bestaudio/best[width<=1080][height<=1920][filesize<1950M]) / "
            "best",
            "--merge-output-format",
            "mp4",
            "--max-filesize",
            "1950M",
            "--post-overwrites",
            "--no-check-certificate",  # زيادة أمان للروابط المحمية
            "--max-filesize",
            "1950M",
            f"{url}",
            "-o",
            download_path_template,
            "--newline",
        ]
    )

    # --- 🟢 منطق التحميل والتعامل الذكي (Async الكامل - الحل الجذري) ---
    if not is_local_file:
        log.info(f"🌐 رابط ويب، جاري التحميل بنظام Async Subprocess...")

        # استخدام asyncio لضمان السيطرة الكاملة على العملية
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
        )

        # استبدل الجزء القديم بهذا
        from tqdm.notebook import (
            tqdm as tqdm_notebook,
        )  # لضمان عملها بشكل تفاعلي في كولاب

        pbar_dl = tqdm_notebook(
            total=0,
            desc=f"📥 جاري التحميل: {display_title[:20]}",
            unit="B",
            unit_scale=True,
            unit_divisor=1024,
            # التعديل الجذري: إزالة الألوان المسببة للرموز الغريبة وتوسيع الشريط
            bar_format="{desc}: {percentage:3.0f}% |{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]",
            ascii=True,  # استخدام التنسيق القياسي لضمان الوضوح التام
        )

        last_db_update = 0

        # قراءة المخرجات واستخراج البيانات الكاملة (المرونة القصوى)
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            line_str = line.decode().strip()

            # 1. استخراج النسبة والحجم الكلي لـ tqdm
            # نمط يدعم: 10.5% of 100.00MiB
            progress_match = re.search(
                r"(\d+(?:\.\d+)?)\s*%\s*of\s*(\d+(?:\.\d+)?)\s*(KiB|MiB|GiB|B)",
                line_str,
            )
            if progress_match:
                percent = float(progress_match.group(1))
                total_val = float(progress_match.group(2))
                unit = progress_match.group(3)
                mult = {"GiB": 1024**3, "MiB": 1024**2, "KiB": 1024, "B": 1}.get(
                    unit, 1024**2
                )

                if pbar_dl.total == 0 or pbar_dl.total != total_val * mult:
                    pbar_dl.total = total_val * mult
                pbar_dl.n = (percent / 100) * pbar_dl.total
                pbar_dl.refresh()

            # 2. تحديث قاعدة البيانات بالسرعة والوقت المتبقي كل 3 ثواني
            if task_id and (time.time() - last_db_update > 3):
                speed_match = re.search(r"at\s+([\d\.]+(?:k|M|G)?B/s)", line_str)
                eta_match = re.search(r"ETA\s+([\d:]+)", line_str)

                percent_now = int(percent) if "percent" in locals() else 0
                speed_now = speed_match.group(1) if speed_match else "Downloading..."
                status_txt = f"📥 جاري التحميل: {percent_now}%"
                if eta_match:
                    status_txt += f" (متبقي {eta_match.group(1)})"

                try:
                    supabase.table("download_tasks").update(
                        {
                            "progress_percent": percent_now,
                            "status_message": status_txt,
                            "download_speed": speed_now,
                            "status": "processing",
                        }
                    ).eq("id", task_id).execute()
                    last_db_update = time.time()
                except:
                    pass

            # 3. فلترة الطباعة: أخطاء فقط
            if any(x in line_str.upper() for x in ["ERROR", "WARNING", "FAILED"]):
                log.warning(f"⚠️ ALERT_LOG: {line_str}")

        # الانتظار الحقيقي والمطلق لانتهاء العملية
        # الانتظار الحقيقي والمطلق لانتهاء العملية
        await process.wait()
        pbar_dl.close()

        # سطر أمان إضافي: اطبع مخرجات الخطأ لو العملية فشلت
        if process.returncode != 0:
            log.error(f"❌ فشل محرك التحميل! كود الخطأ: {process.returncode}")
        # --- ⚡ التعديل المنقذ للوحش ⚡ ---

        await asyncio.sleep(5)

        actual_downloaded_path = None

        # محاولة البحث في المجلد المخصص أولاً، ثم المجلد الحالي كخطة بديلة
        search_locations = [extract_dir, os.getcwd()]

        for loc in search_locations:
            if not os.path.exists(loc):
                continue

            all_files = [os.path.join(loc, f) for f in os.listdir(loc)]
            # فلترة الملفات (استبعاد المجلدات والملفات المؤقتة)
            actual_files = [
                f
                for f in all_files
                if os.path.isfile(f)
                and not f.endswith((".part", ".ytdl", ".temp", ".txt", ".md"))
            ]

            if actual_files:
                # ترتيب حسب وقت التعديل لجلب أحدث ملف نزل فعلاً
                actual_files.sort(key=os.path.getmtime, reverse=True)
                actual_downloaded_path = actual_files[0]
                break  # وجدنا الملف! اخرج من اللوب

        if actual_downloaded_path:
            log.info(f"✅ تم اكتمال التحميل الفعلي: {actual_downloaded_path}")
        else:
            log.error(
                f"❌ فشل التحميل: المجلد فارغ! المحتوى الموجود: {os.listdir(extract_dir)}"
            )

            # --- 🧹 تنظيف الأشباح فور الفشل ---
            if media_id:
                try:
                    # حذف الميديا لأن التحميل فشل
                    supabase.table("medias").delete().eq("id", media_id).execute()
                    log.info(f"🧹 تم حذف سجل الميديا الفارغ (ID: {media_id})")

                    if task_id:
                        supabase.table("download_tasks").update(
                            {
                                "status": "failed",
                                "status_message": "❌ فشل: المجلد فارغ (رابط مكسور)",
                            }
                        ).eq("id", task_id).execute()
                except Exception as clean_err:
                    log.warning(f"⚠️ فشل تنظيف الميديا: {clean_err}")

            # بدلاً من continue اللي سببت المشكلة، هنستخدم return
            # عشان نخرج من "الدالة الحالية" وننهي معالجة الفيلم ده بسلام
            return

    else:
        # حالة الملف المحلي
        log.info(f"⚡ تخطي التحميل: الملف موجود محلياً في {url}")
        actual_downloaded_path = url

        # تعريف متغير وهمي للعملية لتجنب خطأ الـ NameError لاحقاً
        class MockProcess:
            returncode = 0

        process = MockProcess()

    # تحديث سوبابيز قبل بدء المعالجة
    if task_id:
        supabase.table("download_tasks").update(
            {
                "status_message": "⚙️ جاري فحص الملف ومعالجته...",
                "progress_percent": 91,
                "download_speed": "Processing",
            }
        ).eq("id", task_id).execute()

    # --- 2. منطق المعالجة والرفع ---
    if process and process.returncode == 0 and actual_downloaded_path:
        # بكمل باقي الكود عادي (فحص النوع، فك الضغط، جرد الفيديوهات...)
        # فحص الهوية الحقيقية للملف باستخدام أمر النظام
        file_info = subprocess.getoutput(f'file "{actual_downloaded_path}"').lower()
        is_rar = "rar archive" in file_info or "zip archive" in file_info

        if is_rar and not is_local_file:
            log.info("🔓 تم اكتشاف ملف مضغوط حقيقي، جاري البدء في فك التجميع...")
            # (كود فك الضغط واستدعاء run_pyramid_tasks هنا)
        else:
            if is_local_file:
                log.info(f"🎥 معالجة ملف الفيديو المحلي الجاهز: {name}")
            else:
                log.info(f"🎥 تم تحميل فيديو مباشر بنجاح: {name}")

        if is_rar:
            log.info(f"🔓 تم اكتشاف ملف مضغوط حقيقي، جاري فك الضغط...")
            subprocess.run(
                [
                    "unrar",
                    "e",
                    "-y",
                    actual_downloaded_path,
                    os.path.join(extract_dir, ""),
                ],
                capture_output=True,
            )
            if os.path.exists(actual_downloaded_path):
                os.remove(actual_downloaded_path)
        else:
            log.info(f"🎬 تم اكتشاف فيديو، جاري التحضير للرفع...")
            # نقل الفيديو وتغيير اسمه للاسم النظيف للعمل
            # بدلاً من فرض .mp4، استخرج الامتداد الأصلي
            _, file_extension = os.path.splitext(actual_downloaded_path)
            final_video_path = os.path.join(
                extract_dir, f"{clean_name}{file_extension}"
            )
            shutil.move(actual_downloaded_path, final_video_path)

        # 2. جرد الفيديوهات (هذا السطر مهم جداً أن يشمل كل الامتدادات)
        # 1. جرد الفيديوهات
        # 1. جرد الفيديوهات المفكوكة
        # 1. جرد الفيديوهات بذكاء
        all_contents = os.listdir(extract_dir)
        # #print(f"DEBUG: فحص المجلد {extract_dir} وجدنا فيه: {all_contents}")

        videos = [
            os.path.join(extract_dir, f)
            for f in all_contents
            if f.lower().endswith(
                (".mp4", ".mkv", ".avi", ".ts", ".mov", ".webm")
            )  # أضفنا webm و mov
        ]

        # لو لسه مفيش فيديوهات، جرب نبحث عن أي ملف حجمه أكبر من 5 ميجا (أكيد ده الفيديو)
        if not videos:
            for f in all_contents:
                full_p = os.path.join(extract_dir, f)
                if os.path.isfile(full_p) and os.path.getsize(full_p) > 5 * 1024 * 1024:
                    log.info(f"🎯 تم العثور على الفيديو بالحجم وليس الامتداد: {f}")
                    videos.append(full_p)

        videos.sort()
        log.debug(
            f"DEBUG: الملفات الموجودة في المجلد حالياً: {os.listdir(extract_dir)}"
        )
        if not videos:
            log.error("❌ لم يتم العثور على فيديوهات!")
            return

        # --- ⚡ التعديل الجوهري: تحويل المسار لو اكتشفنا أكتر من حلقة ⚡ ---
        if len(videos) > 1:
            log.info(
                f"🎊 كنز! تم اكتشاف {len(videos)} حلقة. جاري إعادة توزيع المهام..."
            )

            new_task_list = []
            for vid in videos:
                v_name = os.path.basename(vid)
                # بناء اسم المهمة الجديد (بندمج اسم المسلسل مع اسم الملف عشان الـ Regex يلقط رقم الحلقة)
                full_task_name = f"{display_title} {v_name}"

                new_task_list.append(
                    {
                        "url": vid,  # بنمرر مسار الملف المحلي كـ URL
                        "name": full_task_name,
                    }
                )

            # تحديث حالة المهمة الأم في سوبابيز قبل القفل
            if task_id:
                supabase.table("download_tasks").update(
                    {
                        "status_message": f"✅ تم تفكيك الملف لـ {len(videos)} حلقة، جاري المعالجة الفردية...",
                        "status": "completed",
                    }
                ).eq("id", task_id).execute()

            # إرسال المهام للمايسترو ليقوم بمعالجة كل حلقة كأنها "تاسك منفصل"
            await run_pyramid_tasks(new_task_list)

            # تنظيف المجلد الأصلي بعد انتهاء كل المهام الفرعية
            if os.path.exists(extract_dir):
                shutil.rmtree(extract_dir)
            return  # إنهاء الدالة الحالية هنا لأنها "فرخت" مهام جديدة
        # --- نهاية التعديل ---
        # 2. جلب البيانات الذكية (الاعتماد الكلي على قاعدة البيانات)
        log.info(f"✅ تم اعتماد البيانات المجلوبة مسبقاً لـ: {display_title}")

        log.info(
            f"✅ تم اكتشاف {len(videos)} ملف. جاري المعالجة والرفع باسم: {display_title}"
        )
        # 3. تحديد الحجم الكلي لكل حلقة
        for idx, vid_path in enumerate(videos, 1):
            # --- [ بداية منطقة التحصين والتمويه - EGY PYRAMID ] ---
            try:
                # إنشاء مسار للملف المموه في نفس مجلد الفيديو الحالي
                extract_dir_current = os.path.dirname(vid_path)
                disguised_file = os.path.join(
                    extract_dir_current, f"disguised_{idx}.mp4"
                )

                log.info(
                    f"🕵️ جاري تطبيق التمويه لكسر البصمة: {os.path.basename(vid_path)}"
                )

                # تأكد أن LOGO_FILE معرف في بداية السكريبت
                # أولاً: نحصل على مدة الفيديو بالثواني (لإظهار النص في نصف الوقت بالضبط)

                def get_duration(file):
                    cmd = f'ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "{file}"'
                    return float(subprocess.check_output(cmd, shell=True))

                # تجهيز النص العربي
                raw_text = "To see more, please search on Google for EGY PYRAMID"
                reshaped_text = arabic_reshaper.reshape(raw_text)
                bidi_text = get_display(reshaped_text)  # النص الآن جاهز للعرض الصحيح

                duration = get_duration(vid_path)
                mid_time = duration / 2

                # ثانياً: أمر FFmpeg المطور
                ffmpeg_cmd = (
                    f'ffmpeg -y -i "{vid_path}" -i "{LOGO_FILE}" -filter_complex '
                    f'"[0:v]scale=iw*1.05:-1,crop=iw/1.05:ih/1.05,eq=gamma=1.05:contrast=1.03[v_final]; '
                    # اللوجو النصي (أول 10 ثواني)
                    f"[v_final]drawtext=text='EGY PYRAMID':fontcolor=0xFFD700:fontsize=80:x=(w-text_w)/2:y=(h-text_h)/2:enable='between(t,0,10)'[txt1]; "
                    # النص العربي (منتصف الفيلم)
                    f"[txt1]drawtext=text='{bidi_text}':fontfile=/content/arial.ttf:fontcolor=0xFFD700:fontsize=w/35:x=(w-text_w)/2:y=h-th-40:"
                    f"enable='between(t,{mid_time},{mid_time+10})'[txt2]; "
                    # سطر التحكم في شفافية اللوجو الصوري
                    f"[1:v]format=rgba,colorchannelmixer=aa=1.0[logo_bright]; "
                    f"[txt2][logo_bright]overlay=W-w-20:20[outv]"
                    f'" '  # قفلنا الفلتر كومبلكس هنا
                    f'-map "[outv]" -map 0:a '  # سحبنا الصوت الأصلي (0:a) كما هو لضمان التزامن 100%
                    f"-c:v libx264 -preset ultrafast -crf 26 -maxrate 1.8M -bufsize 3.6M -threads 0 -pix_fmt yuv420p "
                    f'-c:a aac -b:a 128k -ar 44100 "{disguised_file}"'
                )

                # تنفيذ الأمر (استخدام subprocess.run يضمن الانتظار حتى انتهاء التمويه)
                subprocess.run(ffmpeg_cmd, shell=True, check=True)

                # الاستبدال المادي: حذف الأصلي وتسمية المموه باسم الأصلي
                if os.path.exists(disguised_file):
                    os.remove(vid_path)
                    os.rename(disguised_file, vid_path)
                    log.info(f"✅ تم تحصين الحلقة {idx} بنجاح!")

            except Exception as e:
                log.warning(f"⚠️ خطأ في التمويه، سيتم الرفع الأصلي: {e}")
            # --- [ نهاية منطقة التحصين - السكربت سيكمل الرفع الآن بالملف الجديد ] ---

            file_size_gb = os.path.getsize(vid_path) / (1024**3)
            # ... باقي الكود (جلب البيانات، الأرشفة، تليجرام) سيكمل عمله بـ vid_path الجديد

            # محاولة استخراج الاسم النظيف من اسم الملف الفعلي (خاصة في حالة تحميل سيزون كامل)
            current_file_name = os.path.basename(vid_path)
            # إذا كان هناك أكثر من ملف، نستخدم اسم الملف لاستخراج رقم الحلقة بدقة
            if len(videos) > 1:
                # ندمج اسم الميديا مع اسم الملف لضمان استخراج سياق كامل
                loop_display_title = f"{display_title} {current_file_name}"
            else:
                loop_display_title = display_title

            # --- فحص التكرار لكل حلقة في حالة المسلسلات ---
            if category_search == "tv":
                try:
                    c_title_l, c_cat_l, c_season_l, c_ep_l = get_clean_media_data(
                        loop_display_title
                    )

                    # البحث الذكي عن الميديا
                    m_id_l = None
                    m_query = (
                        supabase.table("medias")
                        .select("id, title")
                        .eq("title", c_title_l)
                        .execute()
                    )
                    if m_query.data:
                        m_id_l = m_query.data[0]["id"]
                    else:
                        search_res = (
                            supabase.table("medias")
                            .select("id, title")
                            .ilike("title", f"%{c_title_l}%")
                            .execute()
                        )
                        for row in search_res.data:
                            if normalize_title(row["title"]) == c_title_l:
                                m_id_l = row["id"]
                                break

                    if m_id_l:
                        # البحث عن الموسم
                        s_query = (
                            supabase.table("seasons")
                            .select("id")
                            .eq("media_id", m_id_l)
                            .eq("season_number", c_season_l)
                            .execute()
                        )
                        if s_query.data:
                            s_id_l = s_query.data[0]["id"]
                            # البحث عن الحلقة
                            # التعديل: نتحقق من وجود روابط حقيقية وليس مجرد وجود السجل
                            e_query = (
                                supabase.table("episodes")
                                .select("id")
                                .eq("media_id", m_id_l)
                                .eq("season_id", s_id_l)
                                .eq("episode_number", c_ep_l)
                                .execute()
                            )
                            if e_query.data:
                                # إذا وجدنا الحلقة، نتحقق هل لها روابط؟
                                ep_id_found = e_query.data[0]["id"]
                                links_query = (
                                    supabase.table("links")
                                    .select("id")
                                    .eq("episode_id", ep_id_found)
                                    .execute()
                                )
                                # إذا كانت هناك روابط، إذن هي مكررة فعلاً
                                if links_query.data:
                                    log.info(
                                        f"✅ [تخطي]: الحلقة {c_ep_l} من الموسم {c_season_l} موجودة بالفعل ولها روابط!"
                                    )
                                    continue
                                else:
                                    # إذا لم تكن هناك روابط، فهذا يعني أنها الحلقة التي ننشئها الآن أو حلقة فشلت سابقاً
                                    log.info(
                                        f"🔄 [تحديث]: الحلقة {c_ep_l} موجودة بدون روابط، جاري العمل عليها..."
                                    )
                except Exception as e:
                    log.warning(f"⚠️ فشل فحص تكرار الحلقة: {e}")

            file_name = f"{clean_name}.mp4"
            episode_label = (
                f"{loop_display_title}" if len(videos) == 1 else f"{loop_display_title}"
            )
            import random
            import string

            # توليد 4 رموز عشوائية فقط لكسر "بصمة" الاسم مع الحفاظ على أرقامك
            rand_id = "".join(
                random.choices(string.ascii_lowercase + string.digits, k=4)
            )
            # المعرف الجديد يجمع بين الرمز العشوائي وقيمك الأساسية
            # تنسيق يدمج الأرقام بدون شرطات كثيرة لضمان القبول
            identifier = f"v{rand_id}x{media_id}x{e_id}x{idx}"  # --- تعريف مفاتيح السيرفرات (يجب أن تكون هنا داخل اللوب أو الدالة) ---

            # 3. الرفع للأرشيف (بالاسم النظيف)
            # 3. الرفع للأرشيف
            log.info(f"📦 أرشفة النسخة الكاملة: {episode_label}")
            #archive_url = "Failed_Archive_Upload"
            archive_url = "Disabled" # تغيير القيمة الافتراضية
            final_file_name = f"f_{media_id}_{e_id}_{idx}.mp4"
            
            try:
                pass # إضافة pass لتجاوز هذا الجزء تماماً
                # # --- أضف/عدل هذا الجزء هنا ---
                # if task_id:
                #     supabase.table("download_tasks").update(
                #         {
                #             "status_message": "☁️ جاري الأرشفة (النسخة الخام)...",
                #             "progress_percent": 92,
                #         }
                #     ).eq("id", task_id).execute()
                # # -------------------------
                # # تحديث الحالة للمتصفح: بدء الرفع للأرشيف
                # if e_id:
                #     supabase.table("episodes").update(
                #         {
                #             "status_message": "☁️ جاري الرفع للأرشيف (نسخة احتياطية)",
                #             "progress_percent": 0,  # تصفير العداد للبدء في حساب الرفع
                #         }
                #     ).eq("id", e_id).execute()

                # pbar_archive = tqdm(
                #     total=os.path.getsize(vid_path),
                #     desc=f"☁️ أرشيف (كامل)",
                #     unit="B",
                #     unit_scale=True,
                #     mininterval=3.0,  # تحديث كل 3 ثوانٍ فقط (مثالي للسرعات البطيئة في كولاب)
                #     maxinterval=10.0,
                #     ascii=" █",  # استبدال الهاشتاج بمربعات ناعمة
                #     colour="green",  # اختيار لون الشريط (يعمل في كولاب)
                # )

                # # اسم ملف مشفر تماماً
                # # 1. إنشاء الـ stream وربطه بملف الفيديو
                # stream = ProgressStream(vid_path, pbar_archive, episode_id=e_id)
                # # 2. تمرير الـ stream مباشرة لمكتبة الرفع
                # # الـ stream الآن هو "المخبر" الذي يخبر pbar بكل بايت يخرج
               
            #try:
              
                #     archive_upload(
                #         identifier,
                #         files={
                #             final_file_name: stream
                #         },  # 👈 التعديل هنا: استخدم stream وليس f_data
                #         # إخفاء اسم الفيلم من البيانات الوصفية (Metadata)
                #         metadata={
                #             "title": f"M-{media_id}-E{e_id}",
                #             "mediatype": "movies",
                #             "description": f"Internal ID: {media_id}_{e_id}_{idx}",
                #         },
                #         access_key=ARCHIVE_ACCESS_KEY,
                #         secret_key=ARCHIVE_SECRET_KEY,
                #         verbose=False,
                #     )
                # finally:
                #     stream.close()  # التأكد من إغلاق الملف بعد الرفع
                # stream.close()
                # pbar_archive.close()
                # archive_url = f"https://archive.org/download/{identifier}/{final_file_name}"  # Get the archive URL after successful upload
                # direct_download_url = (
                #     f"https://archive.org/download/{identifier}/{final_file_name}"
                # )
                # # حقن الرابط المباشر في قاعدة البيانات يدوياً
                # supabase.table("links").insert(
                #     {
                #         "episode_id": e_id,
                #         "url": direct_download_url,
                #         "server_name": "archive",
                #         "last_check_status": "valid",
                #     }
                # ).execute()
                # log.info(f"✅ تم ربط الرابط المباشر في سوبابيز: {direct_download_url}")
            except Exception as e:
                log.error(f"❌ خطأ أرشيف: {e}")

            telegram_direct = None  # تعريف أولي لضمان عدم حدوث NameError
            # 4. الرفع لتليجرام (بالاسم النظيف) مع حماية كاملة
            try:
                if e_id:
                    supabase.table("episodes").update(
                        {
                            "status_message": "📤 جاري الرفع إلى تليجرام...",
                            "progress_percent": 0,
                        }
                    ).eq("id", e_id).execute()

                if file_size_gb > 1.9:
                    log.info(f"✂️ الملف كبير ({file_size_gb:.2f}GB)، جاري التقسيم...")
                    duration_cmd = f'ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "{vid_path}"'
                    total_seconds = float(
                        subprocess.check_output(duration_cmd, shell=True)
                    )
                    half_time = total_seconds / 2
                    part1, part2 = f"{vid_path}_part1.mp4", f"{vid_path}_part2.mp4"

                    subprocess.run(
                        f'ffmpeg -i "{vid_path}" -t {half_time} -c copy "{part1}" -ss {half_time} -c copy "{part2}"',
                        shell=True,
                        check=True,
                    )

                    await upload_to_telegram_only(
                        part1, f"{episode_label} - ج1", episode_id=e_id
                    )
                    await upload_to_telegram_only(
                        part2, f"{episode_label} - ج2", episode_id=e_id
                    )

                    if os.path.exists(part1):
                        os.remove(part1)
                    if os.path.exists(part2):
                        os.remove(part2)
                else:
                    # رفع الملف ككتلة واحدة إذا كان أصغر من 1.9 جيجا
                    # رفع الملف واستقبال الرابط المباشر في المتغير المطلوب
                    telegram_direct = await upload_to_telegram_only(
                        vid_path, episode_label, episode_id=e_id
                    )

            except Exception as e:
                log.warning(
                    f"⚠️ تنبيه: فشل رفع تليجرام ({e})، لكن الوحش مكمل للسيرفرات التانية..."
                )
                if e_id:
                    supabase.table("episodes").update(
                        {
                            "status_message": "⚠️ تليجرام فشل - جاري الرفع للسيرفرات البديلة",
                        }
                    ).eq(
                        "id", e_id
                    ).execute()  # تخطي باقي المراحل لهذا الملف والانتقال للملف التالي

            # --- 5. الرفع المتوازي للرباعي (Voe + Dood + Tape + Lulu) عبر الأرشيف ---
            # --- 5. الرفع المتوازي الخماسي (VK محلي + الباقي ريموت) ---
            if identifier:
                # --- التعديل هنا (إظهار السيرفرات) ---
                if task_id:
                    supabase.table("download_tasks").update(
                        {
                            "status_message": "🚀 ضخ السيرفرات: VK, Voe, Dood, Tape, Lulu",
                            "progress_percent": 95,
                        }
                    ).eq("id", task_id).execute()
                # ------------------------------------
                log.info(
                    f"🚀 البدء في الرفع المتوازي الخماسي (VK + Voe + Dood + Tape + Lulu)..."
                )

                if e_id:
                    supabase.table("episodes").update(
                        {
                            "status_message": "🚀 جاري ضخ الملف لـ VK والرفع المتوازي للبقية...",
                            "progress_percent": 90,
                        }
                    ).eq("id", e_id).execute()
                # --- ⚡ التحول للحل البديل (Telegram Fallback) ⚡ ---
                if not (archive_url and "archive.org" in archive_url):
                    retry_wait = 0
                    while not telegram_direct and retry_wait < 2:
                        log.info(f"⏳ انتظار رابط تليجرام.. محاولة {retry_wait+1}")
                        await asyncio.sleep(5)
                        retry_wait += 1 

                if archive_url and "archive.org" in archive_url:
                    remote_source = identifier
                    log.info(f"✅ المصدر المعتمد للرفع: Archive.org ({identifier})")
                elif telegram_direct:
                    remote_source = telegram_direct
                    log.warning(
                        f"⚠️ تحذير: الأرشيف معطل.. تم استخدام رابط Telegram المباشر كمصدر!"
                    )
                else:
                    remote_source = None
                    log.error(
                        "❌ خطأ قاتل: لا يوجد مصدر (أرشيف أو تليجرام) للرفع المتوازي!"
                    )

                log.info(f"📡 القيمة المرسلة لمهام الرفع: {remote_source}")

                await asyncio.sleep(10)
                # 1. تحضير مهام الريموت باستخدام المصدر المتاح (أرشيف أو تليجرام)
                if remote_source:
                    task_voe = upload_to_voe_api(vid_path, remote_source)
                    await asyncio.sleep(30)
                    task_dood = upload_to_doodstream(
                        dood_api_key, remote_source, final_file_name
                    )
                    await asyncio.sleep(30)
                    task_tape = upload_to_streamtape(
                        st_login, st_key, remote_source, final_file_name
                    )
                    await asyncio.sleep(30)
                    task_lulu = upload_to_lulustream(
                        lu_key, remote_source, final_file_name
                    )
                else:
                    # في حالة انعدام المصادر، نضع مهام وهمية تعيد None
                    task_voe = task_dood = task_tape = task_lulu = asyncio.sleep(
                        0, result=None
                    )

                # 2. تحضير مهمة VK (رفع محلي ثقيل لا يحتاج لرابط ريموت)
                loop = asyncio.get_event_loop()
                task_vk = loop.run_in_executor(
                    None, upload_to_vk_local, episode_label, vid_path
                )

                # 3. إطلاق الصواريخ الخمسة معاً وانتظار الجميع
                # الترتيب مهم جداً لاستلام النتائج بشكل صحيح
                vk_result, file_id, d_url, s_url, lu_url = await asyncio.gather(
                    task_vk, task_voe, task_dood, task_tape, task_lulu
                )

                # تعيين رابط VK المستخرج
                vk_url = vk_result if vk_result else "Failed"

                # --- 6. معالجة النتائج وحفظها ---
                # نتائج VK (إضافة الحفظ لسوبابيز)
                if vk_url != "Failed":
                    supabase.table("links").upsert(
                        {"episode_id": e_id, "server_name": "vk", "url": vk_url},
                        on_conflict="episode_id, server_name",
                    ).execute()
                    log.info(f"✅ VK Link Saved to Supabase!")

                # نتائج Voe
                voe_watch = f"https://voe.sx/e/{file_id}" if file_id else "Failed"

                voe_down = (
                    f"https://voe.sx/{file_id}/download" if file_id else "Failed"
                )  # أضف هذا السطر
                if file_id:
                    log.info(f"✅ Voe Saved! ID: {file_id}")

                # نتائج DoodStream
                if d_url:
                    supabase.table("links").upsert(
                        {"episode_id": e_id, "server_name": "doodstream", "url": d_url},
                        on_conflict="episode_id, server_name",
                    ).execute()
                    log.info(f"✅ DoodStream Saved!")

                # نتائج Streamtape
                if s_url:
                    supabase.table("links").upsert(
                        {"episode_id": e_id, "server_name": "streamtape", "url": s_url},
                        on_conflict="episode_id, server_name",
                    ).execute()
                    log.info(f"✅ Streamtape Saved!")

                # نتائج LuluStream (إضافة الحفظ لسوبابيز)
                if lu_url:
                    supabase.table("links").upsert(
                        {
                            "episode_id": e_id,
                            "server_name": "lulustream",
                            "url": lu_url,
                        },
                        on_conflict="episode_id, server_name",
                    ).execute()
                    log.info(f"✅ LuluStream Saved!")

            try:
                # التعديل: استلام 4 قيم ليتوافق مع الـ Return الجديد للدالة
                e_id, media_id, meta_story, final_poster = save_to_supabase(
                    voe_watch,
                    voe_down,
                    "Pending",
                    loop_display_title,
                    original_task_name,
                    meta_story,
                    final_poster,
                    meta_year,
                    meta_rating,
                    identifier,
                    archive_url,
                    tmdb_id=tmdb_id_fetched,
                    labels=meta_labels,
                    runtime=meta_runtime,
                    duration_iso=meta_duration,
                )
            except Exception as e:
                log.warning(f"⚠️ فشل تحديث ساب باز الأولي: {e}")

            # --- 9. الرفع لـ MixDrop (ضع الكود الجديد هنا) ---
            try:
                if e_id:
                    supabase.table("episodes").update(
                        {
                            "status_message": "💧 جاري الرفع لـ MixDrop...",
                            "progress_percent": 99,
                        }
                    ).eq("id", e_id).execute()

                mix_url = await upload_to_mixdrop(vid_path, mix_user, mix_key)
                if mix_url:
                    supabase.table("links").upsert(
                        {"episode_id": e_id, "server_name": "mixdrop", "url": mix_url},
                        on_conflict="episode_id, server_name",
                    ).execute()
                    log.info(f"✅ تم حفظ رابط MixDrop")
            except Exception as e:
                log.warning(f"⚠️ فشل MixDrop: {e}")

            # --- التحديث النهائي الشامل لجدول الحلقات (خارج الـ try الخاص بـ دود ستريم) ---
            # --- التحديث النهائي الشامل لجدول الحلقات ---
            try:
                # 1. حفظ البيانات واستلام الـ ID (المفتاح القاطع)
                e_id, media_id, meta_story, final_poster = save_to_supabase(
                    voe_watch,
                    voe_down,
                    vk_url,
                    loop_display_title,
                    original_task_name,
                    meta_story,
                    final_poster,
                    meta_year,
                    meta_rating,
                    identifier,
                    archive_url,
                    tmdb_id=tmdb_id_fetched,
                    labels=meta_labels,
                    runtime=meta_runtime,
                    duration_iso=meta_duration,
                )

                # --- ⚡ بلوك النجاح (يجب أن يكون هنا وليس في الـ except) ⚡ ---

                # 2. تحضير بيانات تليجرام من الذاكرة الحية
                # 2. تحضير بيانات تليجرام من الذاكرة الحية (زي ما هي)
                row_data_for_tg = {
                    "title": loop_display_title,
                    "story": meta_story if meta_story else "لا يوجد وصف متاح حالياً.",
                    "poster_url": final_poster,
                    "labels": meta_labels,
                    "year": meta_year,
                }

                # 3. إرسال تمبلت تليجرام (التعديل هنا)
                # بنبعت النوع الحقيقي اللي "الوحش" عرفه من TMDB أو من فحص الرابط
                status = send_to_telegram(
                    row=row_data_for_tg,
                    content_type=category_search,  # <--- استخدم المتغير ده بدل الشرط اليدوي
                    action_text="المشاهدة",
                    post_url=final_poster,  # يفضل وضع رابط المقال الفعلي لو متاح
                    lang_val="لغة أصلية (مترجم)",
                )

                if status:
                    log.info(f"✅ كولاب أرسل تمبلت تليجرام بنجاح")

                # 4. فحص الجودة قبل تفعيل الجاهزية (المنطق الجديد)
                quality_pass = False
                if media_id:
                    # التحقق من وجود 3 سيرفرات على الأقل
                    link_check = (
                        supabase.table("links")
                        .select("id", count="exact")
                        .eq("episode_id", e_id)
                        .execute()
                    )
                    links_count = (
                        link_check.count if link_check.count is not None else 0
                    )

                    # التحقق من وجود بوستر ووصف (ليسوا فارغين)
                    has_metadata = bool(meta_story and meta_story.strip()) and bool(
                        final_poster and final_poster.strip()
                    )

                    # المنطق الجديد: النجاح يعتمد على الروابط فقط، والجاهزية تعتمد على الكل
                    if links_count >= 3:
                        quality_pass = True  # اعتبر المهمة نجحت طالما فيه لينكات

                        if has_metadata:
                            # لو فيه لينكات + داتا = أطلق الجاهزية فوراً
                            supabase.table("medias").update({"is_ready": True}).eq(
                                "id", media_id
                            ).execute()
                            log.info(
                                f"🚀 تم إطلاق إشارة الجاهزية الكاملة (سيرفرات: {links_count})"
                            )
                        else:
                            # لو فيه لينكات بس مفيش داتا = سيبها False واطبع تحذير
                            log.warning(
                                f"🟡 تم الحفظ بنجاح ولكن بدون جاهزية (نقص في الصورة أو الوصف)"
                            )
                    else:
                        quality_pass = False  # هنا فعلاً فشل لأن مفيش لينكات كافية

                # 5. إغلاق المهمة (حذف فقط في حالة انعدام الروابط)
                if task_id:
                    if media_id and not quality_pass:
                        # الحذف هنا فقط لو السيرفرات أقل من 3
                        supabase.table("medias").delete().eq("id", media_id).execute()
                        log.warning(f"🗑️ تم حذف الميديا لعدم وجود روابط كافية.")

                        supabase.table("download_tasks").update(
                            {
                                "status": "failed",
                                "status_message": "❌ فشل: السيرفرات أقل من 3",
                            }
                        ).eq("id", task_id).execute()
                    else:
                        # هنا هيدخل لو quality_pass بـ True (سواء بـ is_ready أو لأ)
                        msg = (
                            "✅ اكتملت بنجاح!"
                            if has_metadata
                            else "⚠️ اكتملت بنجاح (يرجى إضافة الصورة والوصف يدوياً)"
                        )
                        supabase.table("download_tasks").update(
                            {
                                "status": "completed",
                                "progress_percent": 100,
                                "status_message": msg,
                            }
                        ).eq("id", task_id).execute()

            except Exception as e:
                # الـ except دي وظيفتها تبلغك لو الـ try اللي فوق فشلت
                log.error(f"❌ فشل التحديث النهائي أو الإرسال: {e}")

            # 6. تنظيف الملف المحلي (خارج الـ try/except لضمان التنفيذ)
            if os.path.exists(vid_path):
                try:
                    os.remove(vid_path)
                    log.info(f"🗑️ تم تنظيف الملف المحلي: {os.path.basename(vid_path)}")
                except Exception as e:
                    log.warning(f"⚠️ لم يتم مسح الملف المؤقت: {e}")

            # --- هذا هو المكان الصحيح للكود الجديد ---
            # تحديث الحالة النهائية للحلقة (بمحاذاة بلوك الـ try/except بالأعلى)
            try:
                supabase.table("episodes").update(
                    {
                        "progress_percent": 100,
                        "status_message": "✅ اكتملت المعالجة والرفع بنجاح",
                        "download_speed": "Done",
                    }
                ).eq("id", e_id).execute()
            except:
                pass

        # --- خارج لووب الحلقات: مسح المجلد بالكامل ---
        if os.path.exists(extract_dir):
            shutil.rmtree(extract_dir)
        log.info(f"\n✨ المهمة انتهت بنجاح!")
        time.sleep(30)  # انتظار 20 ثانية قبل الاغلاق


async def run_pyramid_tasks(task_list):
    if not task_list:
        log.warning("⚠️ تنبيه: قائمة المهام فارغة!")
        return

    for i, task in enumerate(task_list, 1):
        url = task.get("url")
        name = task.get("name")

        if not url:
            continue

        log.info(f"\n🎬 معالجة ({i}/{len(task_list)}): {name}")
        try:
            # التأكد إن الوحش هيستلم الرابط أو المسار صح
            await pyramid_ultimate_beast(url, name)
        except Exception as e:
            log.error(f"❌ خطأ في '{name}': {e}")


# التعديل المطلوب لضمان الاستقلالية التامة
async def start_download_process(url, name):
    """المدخل الرئيسي - يدعم كاجل، كولاب، والجهاز المحلي"""
    log.info(f"\n🚀 انطلاق الوحش لمعالجة: {name}")
    try:
        # 1. فحص البيئة وتحديد المسار الآمن للكتابة
        if os.path.exists("/kaggle/working"):
            target_path = "/kaggle/working"
        elif os.path.exists("/content"):  # مسار كولاب الافتراضي
            target_path = "/content"
        else:
            target_path = os.getcwd()  # لو شغال على جهازك الشخصي

        # 2. تغيير المسار والطباعة للتأكد
        os.chdir(target_path)
        log.info(f"📂 بيئة العمل الحالية: {os.getcwd()}")

        # 3. انطلاق المحرك
        await pyramid_ultimate_beast(url, name)

    except Exception as e:
        log.error(f"❌ خطأ كارثي في معالجة '{name}': {e}")
