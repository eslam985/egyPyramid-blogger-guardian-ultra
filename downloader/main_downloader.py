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
                            print(f"🔗 تحديث الرابط (Slug) إلى: {target_slug}")
                            supabase.table("medias").update({"slug": target_slug}).eq(
                                "id", m_id
                            ).execute()
                            generated_slug = target_slug
                        else:
                            generated_slug = current_db_slug

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
        return e_id, m_id, meta_story, final_poster
    except Exception as e:
        print(f"❌ خطأ أثناء الحفظ في ساب باز: {e}")
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
        "Referer": "https://lulustream.com/",
        "Origin": "https://lulustream.com/  ",
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
    "luluvdo": {
        "Referer": "https://luluvdo.com/",
        "Origin": "https://luluvdo.com/",
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
            print("✅ اللوجو جاهز ومؤمن في مجلد الأدوات.")
        except:
            pass
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
    # التعديل: إذا كان المدخل رابطاً، نمرره كما هو لـ get_movie_data ليتعامل معه
    if "http" in original_task_name or original_task_name.startswith(("tt", "tmdb")):
        search_query_clean = original_task_name
    else:
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
        print("⚠️ فشل الحصول على ID من ساب باز، لن نتمكن من عرض التقدم الحي.")

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
        print(f"♻️ اكتشاف ملف محلي: {url} - سيتم تخطي التحميل.")
        actual_downloaded_path = url
    else:
        print(f"📡 رابط ويب، جاري التجهيز للسحب...")

    # إنشاء مجلد العمل
    extract_dir = os.path.join(BASE_DIR, f"extracted_{timestamp}")
    os.makedirs(extract_dir, exist_ok=True)

    # تعريف قالب التحميل
    download_path_template = os.path.join(extract_dir, f"down_{timestamp}.%(ext)s")
    # --------------------------------------------------------

    print(f"📡 جاري فحص الرابط وبدء السحب...")

    # ══════════════════════════════════════════════════════════════
    # فحص مبكر للرابط مع نظام المحاولات المتكررة (Retries)
    # ══════════════════════════════════════════════════════════════
    # ══════════════════════════════════════════════════════════════
    # بدء عملية التحميل مباشرة (بدون فحص مبكر)
    # ══════════════════════════════════════════════════════════════
    if not is_local_file:
        print(f"   🚀 [Direct Start] الرابط معتمد — جاري التحميل فوراً...")

    # هنا ييجي كود الـ yt-dlp بتاعك مباشرة

    # 1. جلب الهيدرز الذكية بناءً على الرابط الممرر للدالة
    smart_headers = get_smart_headers(url)

    # 2. بناء أمر الوحش الموحد لضمان تجاوز الحماية في كل الحالات
    cmd = [
        "yt-dlp",
        "--impersonate",
        "chrome",
        "-v",
        "--no-playlist",
        "--user-agent",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "--add-header",
        "Accept: video/webp,video/apng,video/*,*/*;q=0.8",
        "--add-header",
        "Accept-Language: en-US,en;q=0.9,ar;q=0.8",
        "--no-check-certificate",
        "--socket-timeout",
        "60",
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

    # دعم إضافي لسيرفرات vidtube و cdn-tube
    if "vidtube" in url or "cdn-tube" in url:
        cmd.extend(["--extractor-args", "jwplayer:base-url=https://vidtube.one/"])

    # إضافة الرابط والمخرجات النهائية
    # إضافة الرابط والمخرجات النهائية مع ضمان دمج أفضل فيديو وأفضل صوت
    # تحديد الجودة بذكاء: 1080p بحد أقصى 2GB، وإلا 720p
    # تحديد الجودة بذكاء: 1080p بمعدل نقل بيانات منخفض، أو 720p كخيار آمن جداً
    cmd.extend(
        [
            "-f",
            "(bestvideo[height<=1080][filesize<1950M]+bestaudio/best[height<=1080][filesize<1950M]) / (bestvideo[height<=720][filesize<1950M]+bestaudio/best[height<=720][filesize<1950M]) / (bestvideo[height<=480]+bestaudio/best[height<=480]) / best",
            "--merge-output-format",
            "mp4",
            "--post-overwrites",
            "--no-check-certificate",  # زيادة أمان للروابط المحمية
            "--max-filesize",
            "1950M",
            f"{url}",
            "-o",
            download_path_template,
            "--newline",
            "--progress-template",
            "download:[%(progress._percent_str)s]",
        ]
    )

    # --- 🟢 منطق التحميل والتعامل الذكي (Async الكامل - الحل الجذري) ---
    if not is_local_file:
        print(f"🌐 رابط ويب، جاري التحميل بنظام Async Subprocess...")

        # استخدام asyncio لضمان السيطرة الكاملة على العملية
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
        )

        pbar_dl = tqdm(
            total=100,
            desc=f"📥 جاري التحميل: {display_title[:20]}",
            unit="%",
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]",
            mininterval=1.0,
        )

        last_db_update = 0

        # قراءة المخرجات بشكل غير متزامن (مستحيل يهرب للسطر اللي بعده)
        while True:
            line = await process.stdout.readline()
            if not line:
                break

            line_str = line.decode().strip()
            # print(f"DEBUG_LOG: {line_str}")      # السطر ده هيخليك تشوف الـ yt-dlp بيقول إيه بالظبط وهو بيفشل

            # استخراج النسبة
            match = re.search(r"(\d+(?:\.\d+)?)%", line_str)
            if match:
                current_percent = float(match.group(1))
                pbar_dl.n = current_percent
                pbar_dl.refresh()

                # تحديث سوبابيز كل 3 ثواني
                if task_id and (time.time() - last_db_update > 3):
                    speed_match = re.search(r"(\d+\.?\d+\w+/s)", line_str)
                    speed_str = (
                        speed_match.group(1) if speed_match else "Downloading..."
                    )

                    supabase.table("download_tasks").update(
                        {
                            "progress_percent": int(current_percent),
                            "status_message": f"📥 جاري التحميل: {int(current_percent)}%",
                            "download_speed": speed_str,
                            "status": "processing",
                        }
                    ).eq("id", task_id).execute()
                    last_db_update = time.time()

        # الانتظار الحقيقي والمطلق لانتهاء العملية
        # الانتظار الحقيقي والمطلق لانتهاء العملية
        await process.wait()
        pbar_dl.close()

        # سطر أمان إضافي: اطبع مخرجات الخطأ لو العملية فشلت
        if process.returncode != 0:
            print(f"❌ فشل محرك التحميل! كود الخطأ: {process.returncode}")
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
            print(f"✅ تم اكتمال التحميل الفعلي: {actual_downloaded_path}")
        else:
            # طباعة المحتوى للمساعدة في التشخيص لو فشل تاني
            print(
                f"❌ فشل التحميل: المجلد فارغ! المحتوى الموجود: {os.listdir(extract_dir)}"
            )

    else:
        # حالة الملف المحلي
        print(f"⚡ تخطي التحميل: الملف موجود محلياً في {url}")
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
            print("🔓 تم اكتشاف ملف مضغوط حقيقي، جاري البدء في فك التجميع...")
            # (كود فك الضغط واستدعاء run_pyramid_tasks هنا)
        else:
            if is_local_file:
                print(f"🎥 معالجة ملف الفيديو المحلي الجاهز: {name}")
            else:
                print(f"🎥 تم تحميل فيديو مباشر بنجاح: {name}")

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
        print(f"DEBUG: فحص المجلد {extract_dir} وجدنا فيه: {all_contents}")

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
                    print(f"🎯 تم العثور على الفيديو بالحجم وليس الامتداد: {f}")
                    videos.append(full_p)

        videos.sort()
        print(f"DEBUG: الملفات الموجودة في المجلد حالياً: {os.listdir(extract_dir)}")
        if not videos:
            print("❌ لم يتم العثور على فيديوهات!")
            return

        # --- ⚡ التعديل الجوهري: تحويل المسار لو اكتشفنا أكتر من حلقة ⚡ ---
        if len(videos) > 1:
            print(f"🎊 كنز! تم اكتشاف {len(videos)} حلقة. جاري إعادة توزيع المهام...")

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
        print(f"✅ تم اعتماد البيانات المجلوبة مسبقاً لـ: {display_title}")

        print(
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

                print(f"🕵️ جاري تطبيق التمويه لكسر البصمة: {os.path.basename(vid_path)}")

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
                    f'"[0:v]setpts=0.99*PTS,scale=iw*1.05:-1,crop=iw/1.05:ih/1.05,eq=gamma=1.03:contrast=1.02[v_speed]; '
                    # اللوجو النصي (أول 10 ثواني)
                    f"[v_speed]drawtext=text='EGY PYRAMID':fontcolor=0xFFD700:fontsize=80:x=(w-text_w)/2:y=(h-text_h)/2:enable='between(t,0,10)'[txt1]; "
                    # النص العربي (منتصف الفيلم)
                    f"[txt1]drawtext=text='{bidi_text}':fontfile=/content/arial.ttf:fontcolor=0xFFD700:fontsize=w/35:x=(w-text_w)/2:y=h-th-40:"
                    f"enable='between(t,{mid_time},{mid_time+10})'[txt2]; "
                    # سطر التحكم في شفافية اللوجو الصوري (1.0 تعني ظهور كامل بدون باهتان)
                    f"[1:v]format=rgba,colorchannelmixer=aa=1.0[logo_bright]; "
                    f"[txt2][logo_bright]overlay=W-w-20:20[outv]; "
                    f'[0:a]atempo=1.0101[outa]" '
                    f'-map "[outv]" -map "[outa]" '
                    f"-r 23.976 "
                    f"-c:v libx264 -preset superfast -crf 24 -maxrate 2.1M -bufsize 4.2M -pix_fmt yuv420p "
                    f'-c:a aac -b:a 128k -ar 44100 "{disguised_file}"'
                )

                # تنفيذ الأمر (استخدام subprocess.run يضمن الانتظار حتى انتهاء التمويه)
                subprocess.run(ffmpeg_cmd, shell=True, check=True)

                # الاستبدال المادي: حذف الأصلي وتسمية المموه باسم الأصلي
                if os.path.exists(disguised_file):
                    os.remove(vid_path)
                    os.rename(disguised_file, vid_path)
                    print(f"✅ تم تحصين الحلقة {idx} بنجاح!")

            except Exception as e:
                print(f"⚠️ خطأ في التمويه، سيتم الرفع الأصلي: {e}")
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
            identifier = f"egy-pyr-{media_id}-{e_id}-{idx}".replace("_", "-").replace(" ", "-")
            # --- تعريف مفاتيح السيرفرات (يجب أن تكون هنا داخل اللوب أو الدالة) ---

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
                # بدلاً من استخدام clean_name، سنستخدم نفس هيكلة الـ IDs لاسم الملف
                final_file_name = f"vid__{media_id}_{e_id}_{idx}.mp4"

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
                archive_url = f"https://archive.org/download/{identifier}/{final_file_name}"  # Get the archive URL after successful upload
                direct_download_url = (
                    f"https://archive.org/download/{identifier}/{final_file_name}"
                )
                # حقن الرابط المباشر في قاعدة البيانات يدوياً
                supabase.table("links").insert(
                    {
                        "episode_id": e_id,
                        "url": direct_download_url,
                        "server_name": "archive",
                        "last_check_status": "valid",
                    }
                ).execute()
                print(f"✅ تم ربط الرابط المباشر في سوبابيز: {direct_download_url}")
            except Exception as e:
                print(f"❌ خطأ أرشيف: {e}")
                
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
                    # رفع الملف واستقبال الرابط المباشر في المتغير المطلوب
                    telegram_direct = await upload_to_telegram_only(vid_path, episode_label, episode_id=e_id)

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
                # --- ⚡ التحول للحل البديل (Telegram Fallback) ⚡ ---
                # نتحقق: هل الأرشيف نجح؟ (لو archive_url لا يحتوي على رابط صحيح، نستخدم تليجرام)
                if archive_url and "archive.org" in archive_url:
                    remote_source = identifier
                    print(f"✅ المصدر المعتمد للرفع: Archive.org ({identifier})")
                elif telegram_direct:
                    remote_source = telegram_direct
                    print(f"⚠️ تحذير: الأرشيف معطل.. تم استخدام رابط Telegram المباشر كمصدر!")
                else:
                    remote_source = None
                    print("❌ خطأ قاتل: لا يوجد مصدر (أرشيف أو تليجرام) للرفع المتوازي!")
                    
                    
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
                    task_lulu = upload_to_lulustream(lu_key, remote_source, final_file_name)
                else:
                    # في حالة انعدام المصادر، نضع مهام وهمية تعيد None
                    task_voe = task_dood = task_tape = task_lulu = asyncio.sleep(0, result=None)

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

                mix_url = await upload_to_mixdrop(vid_path, mix_user, mix_key)
                if mix_url:
                    supabase.table("links").upsert(
                        {"episode_id": e_id, "server_name": "mixdrop", "url": mix_url},
                        on_conflict="episode_id, server_name",
                    ).execute()
                    print(f"✅ تم حفظ رابط MixDrop")
            except Exception as e:
                print(f"⚠️ فشل MixDrop: {e}")

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
                row_data_for_tg = {
                    "title": loop_display_title,
                    "story": meta_story if meta_story else "لا يوجد وصف متاح حالياً.",
                    "poster_url": final_poster,
                    "labels": meta_labels,
                    "year": meta_year,
                }

                # 3. إرسال تمبلت تليجرام
                status = send_to_telegram(
                    row=row_data_for_tg,
                    content_type="MOVIE" if "فيلم" in display_title else "SERIES",
                    action_text="المشاهدة",
                    post_url="https://egypyramid.vercel.app/",
                    lang_val="مترجم / مدبلج",
                )

                if status:
                    print(f"✅ كولاب أرسل تمبلت تليجرام بنجاح")

                # 4. تفعيل الجاهزية بالـ ID المباشر (القاضية)
                if media_id:
                    supabase.table("medias").update({"is_ready": True}).eq(
                        "id", media_id
                    ).execute()
                    print(f"🚀 تم إطلاق إشارة الجاهزية للميديا رقم: {media_id}")

                # 5. إغلاق المهمة في download_tasks
                if task_id:
                    supabase.table("download_tasks").update(
                        {
                            "status": "completed",
                            "progress_percent": 100,
                            "status_message": "✅ اكتملت جميع المراحل بنجاح!",
                        }
                    ).eq("id", task_id).execute()

            except Exception as e:
                # الـ except دي وظيفتها تبلغك لو الـ try اللي فوق فشلت
                print(f"❌ فشل التحديث النهائي أو الإرسال: {e}")

            # 6. تنظيف الملف المحلي (خارج الـ try/except لضمان التنفيذ)
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
    if not task_list:
        print("⚠️ تنبيه: قائمة المهام فارغة!")
        return

    for i, task in enumerate(task_list, 1):
        url = task.get("url")
        name = task.get("name")

        if not url:
            continue

        print(f"\n🎬 معالجة ({i}/{len(task_list)}): {name}")
        try:
            # التأكد إن الوحش هيستلم الرابط أو المسار صح
            await pyramid_ultimate_beast(url, name)
        except Exception as e:
            print(f"❌ خطأ في '{name}': {e}")


# التعديل المطلوب لضمان الاستقلالية التامة
async def start_download_process(url, name):
    """المدخل الرئيسي - يدعم كاجل، كولاب، والجهاز المحلي"""
    print(f"\n🚀 انطلاق الوحش لمعالجة: {name}")
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
        print(f"📂 بيئة العمل الحالية: {os.getcwd()}")

        # 3. انطلاق المحرك
        await pyramid_ultimate_beast(url, name)

    except Exception as e:
        print(f"❌ خطأ كارثي في معالجة '{name}': {e}")
