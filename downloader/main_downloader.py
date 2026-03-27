import os
import time
import re
import shutil
import subprocess
import nest_asyncio
from urllib.parse import unquote
import asyncio
from internetarchive import upload as archive_upload
from urllib.parse import urlparse

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

# 3. تنظيف استيراد سوبابيز
try:
    from supabase import create_client, Client as SupabaseClient
except ImportError:
    print("❌ خطأ: مكتبة supabase غير مثبتة.")

# تفعيل nest_asyncio
nest_asyncio.apply()

# تثبيت بيئة tqdm عالمياً داخل هذا الملف أيضاً
os.environ["TQDM_MININTERVAL"] = "2.0"

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: SupabaseClient = create_client(SUPABASE_URL, SUPABASE_KEY)


# استدعاء المفاتيح من البيئة بدلاً من كتابتها يدوياً
ARCHIVE_ACCESS_KEY = os.getenv("ARCHIVE_ACCESS_KEY")
ARCHIVE_SECRET_KEY = os.getenv("ARCHIVE_SECRET_KEY")
lu_key = os.getenv("LULUSTREAM_API_KEY")
lu_key = os.getenv("LULUSTREAM_API_KEY")


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
        generated_slug = c_title.lower().replace(" ", "-")
        generated_slug = re.sub(
            r"[^a-z0-9\u0600-\u06FF-]", "", generated_slug
        )  # دعم العربي في الـ slug

        media_payload = {
            "tmdb_id": str(tmdb_id) if tmdb_id else None,
            "title": c_title,
            "story": meta_story,
            "poster_url": final_poster,
            "category": c_cat,  # movie or tv
            "media_type": c_cat,  # نملأ media_type بنفس قيمة category كبداية ذكية
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
                    # ✅ وجدناه! خذ الـ ID
                    m_id = query.data[0]["id"]

                    # --- التعديل: قراءة البيانات "لحساب" المتغيرات وليس للتعديل ---
                    # بنسحب القصة والبوستر من سوبابيز عشان نستخدمهم في تليجرام صح
                    existing_data = query.data[0]

                    if existing_data.get("story"):
                        meta_story = existing_data["story"]
                    if existing_data.get("poster_url"):
                        final_poster = existing_data["poster_url"]

                    print(
                        f"🛡️ [حماية]: تم العثور على '{c_title}' (ID: {m_id})، تم سحب البيانات للأرشفة دون تعديل."
                    )
                else:
                    # ✨ مش موجود خالص؟ إذن أنشئه "مرة واحدة فقط"
                    print(f"🆕 [إنشاء]: سجل جديد لـ '{c_title}'...")
                    # هنا نستخدم insert وليس upsert ليكون أكثر أماناً
                    new_media = supabase.table("medias").insert(media_payload).execute()
                    if new_media.data:
                        m_id = new_media.data[0]["id"]

                break  # إذا وصلنا هنا بنجاح، نخرج من حلقة المحاولات
            except Exception as e:
                if attempt < 2:
                    print(
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
            print(f"📡 جاري معالجة الموسم رقم {season_number} للميديا {m_id}...")
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
                    print(f"✅ تم العثور على الموسم في القاعدة بـ ID: {s_id}")
                else:
                    print(f"🆕 الموسم {season_number} غير موجود، جاري إنشاؤه...")
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
                        print(f"✅ تم إنشاء موسم جديد بـ ID: {s_id}")
            except Exception as se:
                print(f"⚠️ خطأ في إنشاء الموسم: {se}")

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
                    print(f"⚠️ خطأ في معالجة التصنيف {g_name}: {ge}")

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
                        print(
                            f"⚠️ سوبابيز مشغول (502/Timeout)، محاولة رقم {attempt+1} خلال 3 ثوانٍ..."
                        )
                        time.sleep(3)
                    else:
                        print(
                            f"❌ فشل تسجيل رابط {entry['server_name']} بعد 3 محاولات: {link_err}"
                        )
        return e_id, meta_story, final_poster
    except Exception as e:
        print(f"❌ خطأ أثناء الحفظ في ساب باز: {e}")
        return None, meta_story, final_poster


# قائمة "الخداع" للمواقع المختلفة - ضعها في أعلى الملف
SITES_COOKBOOK = {
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

    # هذا السطر سيطبع الآن المسار الحقيقي الصحيح (/content/project في كولاب)
    print(f"🛠️ مسار العمل الحالي للوحش: {os.getcwd()}")
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

    print(f"🔍 جلب بيانات العمل من TMDB/IMDB للتحقق من الأرشيف...")
    # احتفظ بالاسم الأصلي الذي كتبته في التاسك كخطة احتياطية
    original_task_name = str(name).strip()

    # استخراج الاسم النظيف للبحث في TMDB (بدلاً من البحث بالاسم الكامل مع رقم الحلقة)
    search_query_clean, _, _, _ = get_clean_media_data(original_task_name)
    print(f"🔎 البحث عن: {search_query_clean} ...")

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
    ) = get_movie_data(search_query_clean if search_query_clean else name)

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

    is_batch = False  # سنحددها لاحقاً بعد التحميل أو الفحص

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
                    print(f"✅ [تخطي]: الفيلم '{display_title}' موجود بالفعل!")
                    return
            # للمسلسلات: لا يمكننا الفحص هنا لأننا لا نعرف الحلقات الموجودة في الرابط بعد
            # سيتم الفحص داخل لووب الحلقات لاحقاً
    except Exception as e:
        print(f"⚠️ فشل فحص التكرار الأولي: {e}")

    # --- 3. حجز مكان أولي (للمسلسلات سيتم تحديثه لاحقاً لكل حلقة) ---
    # إنشاء identifier مؤقت للتحميل
    temp_id = f"loading_{timestamp}"

    # استدعاء الحفظ الأولي للحصول على e_id
    # استدعاء الحفظ الأولي للحصول على e_id
    # التعديل: استلام 3 قيم بدلاً من واحدة
    e_id, meta_story, final_poster = save_to_supabase(
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
        print("⚠️ فشل الحصول على ID من ساب باز، لن نتمكن من عرض التقدم الحي.")
    # --- 3. استكمال العمل في حال كان الفيلم جديداً ---
    clean_name = (
        "".join([c for c in display_title if c.isalnum() or c in (" ", ".", "_")])
        .strip()
        .replace(" ", "_")
    )

    # أولاً: تعريف وإنشاء المجلد الفريد
    # التعديل لضمان أن المجلد ينشأ في مكان مسموح
    extract_dir = os.path.join(BASE_DIR, f"extracted_{timestamp}")
    os.makedirs(extract_dir, exist_ok=True)

    # ثانياً: تعريف قالب التحميل داخل المجلد المنشأ
    download_path_template = os.path.join(extract_dir, f"down_{timestamp}.%(ext)s")

    print(f"📡 جاري فحص الرابط وبدء السحب...")

    # 1. جلب الهيدرز الذكية بناءً على الرابط الممرر للدالة
    smart_headers = get_smart_headers(url)

    # 2. بناء أمر الوحش المتطور
    # 2. بناء أمر الوحش المتطور
    cmd = (
        [
            "yt-dlp",
            "-v",
            "--no-playlist",
            "--user-agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "--add-header",
            "Accept: video/webp,video/apng,video/*,*/*;q=0.8",
            "--add-header",
            "Accept-Language: en-US,en;q=0.9,ar;q=0.8",
        ]
        + smart_headers  # الهيدرز الذكية
        + [
            # خيارات الأداء
            "--concurrent-fragments",
            "10",
            "--file-access-retries",
            "infinite",
            "--fragment-retries",
            "infinite",
            "--hls-use-mpegts",
            "--no-check-certificate",
            "--socket-timeout",
            "60",
            # خيارات كسر حماية الـ JWPlayer (لا تضع Referer ثابت هنا حتى لا يفسد عمل الهيدرز الذكية)
            "--extractor-args",
            "jwplayer:base-url=https://vidtube.one/",
            "--format",
            "best[ext=mp4]/best",
            "-f",
            "best",
            f"{url}",
            "-o",
            download_path_template,
            "--newline",
            "--progress-template",
            "download:[%(progress._percent_str)s]",
        ]
    )

    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    pbar_dl = tqdm(
        total=100,
        desc=f"📥 جاري التحميل: {display_title[:20]}",
        unit="%",
        bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]",
        mininterval=1.0,  # لن يطبع أي سطر جديد إلا بعد مرور ثانية كاملة مهما كانت السرعة
    )

    last_db_update = 0
    last_percent = 0  # أضف هذا السطر هنا
    for line in process.stdout:
        match = re.search(r"(\d+(?:\.\d+)?)%", line)
        if match:
            current_percent = float(match.group(1))
            # لا تقم بالتحديث إلا إذا زادت النسبة بمقدار 1% على الأقل أو مر وقت كافٍ
            if current_percent - last_percent >= 1.0:
                pbar_dl.n = current_percent  # ضبط القيمة مباشرة بدل الـ update التراكمي
                pbar_dl.refresh()
                last_percent = current_percent

                # تحديث ساب باز كل 3 ثوانٍ بالسرعة والنسبة
                if e_id and (time.time() - last_db_update > 3):
                    # محاولة استخراج السرعة من السطر (تبحث عن نمط مثل 5.2MiB/s)
                    speed_match = re.search(r"(\d+\.?\d+\w+/s)", line)
                    speed_str = (
                        speed_match.group(1) if speed_match else "Downloading..."
                    )

                    # التحديث يذهب لجدول المهام ليظهر في الداشبورد فوراً
                    if task_id:
                        supabase.table("download_tasks").update(
                            {
                                "progress_percent": int(current_percent),
                                "status_message": f"📥 جاري التحميل: {int(current_percent)}%",
                                "download_speed": speed_str,
                                "status": "processing",
                            }
                        ).eq("id", task_id).execute()

    process.wait()
    if process.returncode != 0:
        print(f"❌ فشل yt-dlp في التحميل. الكود البرمجي للخطأ: {process.returncode}")
        # طباعة آخر سطر من الخطأ لفهم السبب
        print("💡 نصيحة: الرابط غالباً انتهت صلاحيته أو محمي بـ IP جهازك.")
    pbar_dl.close()  # ابحث عن هذا السطر

    # --- التعديل هنا ---
    if task_id:
        supabase.table("download_tasks").update(
            {
                "status_message": "⚙️ جاري فحص الملف وفك الضغط...",
                "progress_percent": 91,  # كسر حاجز الـ 100% الوهمي
                "download_speed": "Processing",
            }
        ).eq("id", task_id).execute()
    # ------------------

    # جلب المسار الحقيقي للملف الذي تم تحميله داخل المجلد الفريد
    downloaded_files = [
        os.path.join(extract_dir, f)
        for f in os.listdir(extract_dir)
        if f.startswith(f"down_{timestamp}")
    ]
    actual_downloaded_path = downloaded_files[0] if downloaded_files else None

    if process.returncode == 0 and actual_downloaded_path:
        # فحص الهوية الحقيقية للملف
        file_info = subprocess.getoutput(f'file "{actual_downloaded_path}"').lower()
        is_rar = "rar archive" in file_info or "zip archive" in file_info

        if is_rar:
            print(f"🔓 تم اكتشاف ملف مضغوط حقيقي، جاري فك الضغط...")
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
            print(f"🎬 تم اكتشاف فيديو، جاري التحضير للرفع...")
            # نقل الفيديو وتغيير اسمه للاسم النظيف للعمل
            final_video_path = os.path.join(extract_dir, f"{clean_name}.mp4")
            shutil.move(actual_downloaded_path, final_video_path)

        # 2. جرد الفيديوهات (هذا السطر مهم جداً أن يشمل كل الامتدادات)
        # 1. جرد الفيديوهات
        videos = [
            os.path.join(extract_dir, f)
            for f in os.listdir(extract_dir)
            if f.lower().endswith((".mp4", ".mkv", ".avi", ".ts"))
        ]
        videos.sort()

        if not videos:
            print("❌ لم يتم العثور على فيديوهات!")
            return
        # 2. جلب البيانات الذكية (الاعتماد الكلي على قاعدة البيانات)
        print(f"✅ تم اعتماد البيانات المجلوبة مسبقاً لـ: {display_title}")

        print(
            f"✅ تم اكتشاف {len(videos)} ملف. جاري المعالجة والرفع باسم: {display_title}"
        )

        for idx, vid_path in enumerate(videos, 1):
            file_size_gb = os.path.getsize(vid_path) / (1024**3)

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
                                    print(
                                        f"✅ [تخطي]: الحلقة {c_ep_l} من الموسم {c_season_l} موجودة بالفعل ولها روابط!"
                                    )
                                    continue
                                else:
                                    # إذا لم تكن هناك روابط، فهذا يعني أنها الحلقة التي ننشئها الآن أو حلقة فشلت سابقاً
                                    print(
                                        f"🔄 [تحديث]: الحلقة {c_ep_l} موجودة بدون روابط، جاري العمل عليها..."
                                    )
                except Exception as e:
                    print(f"⚠️ فشل فحص تكرار الحلقة: {e}")

            file_name = f"{clean_name}.mp4"
            episode_label = (
                f"{loop_display_title}" if len(videos) == 1 else f"{loop_display_title}"
            )
            identifier = f"egy_pyr_{timestamp}_e{idx}"
            # --- تعريف مفاتيح السيرفرات (يجب أن تكون هنا داخل اللوب أو الدالة) ---
            dood_api_key = "553856lyhogniqkwh0q9m5"
            st_login = "b4141c9ac5586a160818"
            st_key = "8OmZOAWa2eHora2"

            # 3. الرفع للأرشيف (بالاسم النظيف)
            # 3. الرفع للأرشيف
            print(f"📦 أرشفة النسخة الكاملة: {episode_label}")
            archive_url = "Failed_Archive_Upload"
            try:
                # --- أضف/عدل هذا الجزء هنا ---
                if task_id:
                    supabase.table("download_tasks").update(
                        {
                            "status_message": "☁️ جاري الأرشفة (النسخة الخام)...",
                            "progress_percent": 92,
                        }
                    ).eq("id", task_id).execute()
                # -------------------------
                # تحديث الحالة للمتصفح: بدء الرفع للأرشيف
                if e_id:
                    supabase.table("episodes").update(
                        {
                            "status_message": "☁️ جاري الرفع للأرشيف (نسخة احتياطية)",
                            "progress_percent": 0,  # تصفير العداد للبدء في حساب الرفع
                        }
                    ).eq("id", e_id).execute()

                pbar_archive = tqdm(
                    total=os.path.getsize(vid_path),
                    desc=f"☁️ أرشيف (كامل)",
                    unit="B",
                    unit_scale=True,
                    mininterval=3.0,  # تحديث كل 3 ثوانٍ فقط (مثالي للسرعات البطيئة في كولاب)
                    maxinterval=10.0,
                    ascii=" #",  # استخدام رموز بسيطة لا تربك المتصفح
                )
                # استبدل سطر إنشاء ProgressStream بـ:
                stream = ProgressStream(vid_path, pbar_archive, episode_id=e_id)
                # التعديل: نضمن أن اسم الملف داخل الأرشيف هو اسم الفيلم وليس الرابط أو اسم عشوائي
                final_file_name = f"{clean_name}.mp4"

                archive_upload(
                    identifier,
                    files={final_file_name: stream},  # هنا السر!
                    metadata={"title": episode_label, "mediatype": "movies"},
                    access_key=ARCHIVE_ACCESS_KEY,
                    secret_key=ARCHIVE_SECRET_KEY,
                    verbose=False,
                )
                stream.close()
                pbar_archive.close()
                archive_url = f"https://archive.org/details/{identifier}"  # Get the archive URL after successful upload

            except Exception as e:
                print(f"❌ خطأ أرشيف: {e}")

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
                    print(f"✂️ الملف كبير ({file_size_gb:.2f}GB)، جاري التقسيم...")
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
                    await upload_to_telegram_only(
                        vid_path, episode_label, episode_id=e_id
                    )

            except Exception as e:
                print(f"❌ فشل رفع تليجرام: {e}")
                if e_id:
                    supabase.table("episodes").update(
                        {
                            "status_message": "❌ فشل في مرحلة تليجرام",
                            "download_speed": "Error",
                        }
                    ).eq("id", e_id).execute()
                continue  # تخطي باقي المراحل لهذا الملف والانتقال للملف التالي

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
                print(
                    f"🚀 البدء في الرفع المتوازي الخماسي (VK + Voe + Dood + Tape + Lulu)..."
                )

                if e_id:
                    supabase.table("episodes").update(
                        {
                            "status_message": "🚀 جاري ضخ الملف لـ VK والرفع المتوازي للبقية...",
                            "progress_percent": 90,
                        }
                    ).eq("id", e_id).execute()

                # 1. تحضير مهام الريموت (تستهلك طلبات HTTP فقط)
                task_voe = upload_to_voe_api(vid_path, identifier)
                await asyncio.sleep(20)
                task_dood = upload_to_doodstream(dood_api_key, identifier, file_name)
                await asyncio.sleep(20)
                task_tape = upload_to_streamtape(
                    st_login, st_key, identifier, file_name
                )
                await asyncio.sleep(20)
                task_lulu = upload_to_lulustream(lu_key, identifier, file_name)

                # 2. تحضير مهمة VK (رفع محلي ثقيل) - تشغيلها في Thread منفصل لعدم تعطيل الـ Event Loop
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
                    print(f"✅ VK Link Saved to Supabase!")

                # نتائج Voe
                voe_watch = f"https://voe.sx/e/{file_id}" if file_id else "Failed"

                voe_down = (
                    f"https://voe.sx/{file_id}/download" if file_id else "Failed"
                )  # أضف هذا السطر
                if file_id:
                    print(f"✅ Voe Saved! ID: {file_id}")

                # نتائج DoodStream
                if d_url:
                    supabase.table("links").upsert(
                        {"episode_id": e_id, "server_name": "doodstream", "url": d_url},
                        on_conflict="episode_id, server_name",
                    ).execute()
                    print(f"✅ DoodStream Saved!")

                # نتائج Streamtape
                if s_url:
                    supabase.table("links").upsert(
                        {"episode_id": e_id, "server_name": "streamtape", "url": s_url},
                        on_conflict="episode_id, server_name",
                    ).execute()
                    print(f"✅ Streamtape Saved!")

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
                    print(f"✅ LuluStream Saved!")

            try:
                # التعديل: استلام 3 قيم لضمان تحديث الذاكرة بالقصة والبوستر من سوبابيز
                e_id, meta_story, final_poster = save_to_supabase(
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
                print(f"⚠️ فشل تحديث ساب باز الأولي: {e}")

            # --- 9. الرفع لـ MixDrop (ضع الكود الجديد هنا) ---
            try:
                if e_id:
                    supabase.table("episodes").update(
                        {
                            "status_message": "💧 جاري الرفع لـ MixDrop...",
                            "progress_percent": 99,
                        }
                    ).eq("id", e_id).execute()

                mix_url = await upload_to_mixdrop(
                    vid_path, "ee17172@gmail.com", "3KO11MEVXQZJiWy"
                )
                if mix_url:
                    supabase.table("links").upsert(
                        {"episode_id": e_id, "server_name": "mixdrop", "url": mix_url},
                        on_conflict="episode_id, server_name",
                    ).execute()
                    print(f"✅ تم حفظ رابط MixDrop")
            except Exception as e:
                print(f"⚠️ فشل MixDrop: {e}")

            # --- التحديث النهائي الشامل لجدول الحلقات (خارج الـ try الخاص بـ دود ستريم) ---
            try:
                # التعديل: التحديث النهائي لآخر مرة قبل تليجرام
                e_id, meta_story, final_poster = save_to_supabase(
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
            except Exception as e:
                print(f"❌ فشل التحديث النهائي في سوبابيز: {e}")

            # التعديل: تأكد أننا نرسل رابط البوستر الصحيح من بيانات الميديا (parent_media)
            # ابحث عن استدعاء الدالة واستبدله بهذا المنطق:

            # --- تعديل بلوك الإرسال لضمان استخدام البيانات الحية ---
            try:
                # نقوم بتحديث row_data يدوياً من المتغيرات الموجودة في الذاكرة
                row_data_for_tg = {
                    "title": loop_display_title,
                    "story": meta_story if meta_story else "لا يوجد وصف متاح حالياً.",
                    "poster_url": final_poster,
                    "labels": meta_labels,
                    "year": meta_year,
                }

                status = send_to_telegram(
                    row=row_data_for_tg,  # نرسل القاموس الجديد اللي ملأناه
                    content_type="MOVIE" if "فيلم" in display_title else "SERIES",
                    action_text="المشاهدة",
                    post_url="https://egy-pyramid-drama.blogspot.com/",
                    lang_val="مترجم / مدبلج",
                )
                if status:
                    print(f"✅ كولاب أرسل تمبلت الفيسبوك بنجاح")

                    # --- التعديل النهائي للبشرى السعيدة ---
                    if task_id:
                        supabase.table("download_tasks").update(
                            {
                                "status_message": "✅ اكتملت جميع المراحل بنجاح!",
                                "progress_percent": 100,
                                "download_speed": "Done",
                                "status": "completed",
                            }
                        ).eq("id", task_id).execute()
            except Exception as e:
                print(f"⚠️ فشل كولاب في إرسال التمبلت: {e}")

            # حذف الملف بعد التأكد من انتهاء كل العمليات
            if os.path.exists(vid_path):
                try:
                    os.remove(vid_path)
                    print(f"🗑️ تم تنظيف الملف المحلي: {os.path.basename(vid_path)}")
                except Exception as e:
                    print(f"⚠️ لم يتم مسح الملف المؤقت: {e}")

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
        print(f"\n✨ المهمة انتهت بنجاح!")


async def run_pyramid_tasks(task_list):
    if not task_list or not task_list[0]["url"]:
        print("⚠️ تنبيه: قائمة الروابط فارغة!")
        return

    for i, task in enumerate(task_list, 1):
        print(f"\n🎬 معالجة ({i}/{len(task_list)}): {task['name']}")
        try:
            await pyramid_ultimate_beast(task["url"], task["name"])
        except Exception as e:
            print(f"❌ خطأ في '{task['name']}': {e}")


# التعديل المطلوب لضمان الاستقلالية التامة
async def start_download_process(url, name):
    """المدخل الرئيسي للداشبورد - الآن يعمل بشكل مستقل تماماً"""
    print(f"\n🚀 انطلاق الوحش لمعالجة: {name}")
    try:
        # الحقيقة الصارمة: إجبار الكود على العمل في المجلد المسموح به في كاجل
        if "KAGGLER_WORKING_DIR" in os.environ or os.path.exists("/kaggle/working"):
            os.chdir("/kaggle/working")
            print(f"📂 تم تغيير مسار العمل إلى: {os.getcwd()}")

        # استدعاء المحرك
        await pyramid_ultimate_beast(url, name)
    except Exception as e:
        print(f"❌ خطأ كارثي في معالجة '{name}': {e}")
