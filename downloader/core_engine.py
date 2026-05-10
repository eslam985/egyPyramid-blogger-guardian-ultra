import os
import asyncio
import time
import random
import string
import re
import shutil
import subprocess
import httpx
import arabic_reshaper
from urllib.parse import unquote, urlparse
from tqdm import tqdm as tqdm_std
from bidi.algorithm import get_display

# 1. استيراد اللوجر
try:
    from .logger_setup import get_beast_logger
except ImportError:
    from logger_setup import get_beast_logger
log = get_beast_logger("GuardianUltra")

# 2. استيراد الدوال الخارجية
try:
    from .db_manager import save_to_supabase
    from .utils import get_smart_headers
    from .link_extractor import get_direct_link_via_playwright, get_mixdrop_direct_link
    from .processors import *
    from .engine import send_to_telegram, upload_to_telegram_only, ensure_dependencies
except ImportError:
    from db_manager import save_to_supabase
    from utils import get_smart_headers
    from link_extractor import get_direct_link_via_playwright, get_mixdrop_direct_link
    from processors import *
    from engine import send_to_telegram, upload_to_telegram_only, ensure_dependencies

# 3. تعريف متغيرات البيئة والقاعدة (قبل الدوال) ✅
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

try:
    from supabase import create_client, Client as SupabaseClient

    supabase: SupabaseClient = create_client(SUPABASE_URL, SUPABASE_KEY)
except:
    supabase = None

# مفاتيح الـ API
ARCHIVE_ACCESS_KEY = os.getenv("ARCHIVE_ACCESS_KEY")
ARCHIVE_SECRET_KEY = os.getenv("ARCHIVE_SECRET_KEY")
lu_key = os.getenv("LULUSTREAM_API_KEY")
dood_api_key = os.getenv("DOOD_API_KEY")
st_login = os.getenv("STREAMTAPE_LOGIN")
st_key = os.getenv("STREAMTAPE_KEY")
mix_user = os.getenv("MIXDROP_EMAIL")
mix_key = os.getenv("MIXDROP_API_KEY")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
OMDB_API_KEY = os.getenv("OMDB_API_KEY")
VOE_API_KEY = os.getenv("VOE_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
VK_ACCESS_TOKEN = os.getenv("VK_ACCESS_TOKEN")
VK_GROUP_ID = os.getenv("VK_GROUP_ID")
VK_ALBUM_ID = os.getenv("VK_ALBUM_ID", "2")  # "2" كقيمة افتراضية إذا لم يوجد سكرت
# بناء القاموس من متغيرات البيئة
CLOUDINARY_CONFIG = {
    "cloud_name": os.getenv("CLOUDINARY_CLOUD_NAME"),
    "upload_preset": os.getenv("CLOUDINARY_UPLOAD_PRESET"),
}


# 4. الدوال الوسيطة
async def run_pyramid_tasks(task_list):
    """دالة وسيطة لاستدعاء المايسترو لتجنب الـ Circular Import"""
    try:
        from .main_downloader import run_pyramid_tasks as original_run
    except ImportError:
        from main_downloader import run_pyramid_tasks as original_run
    return await original_run(task_list)


# --- دالة pyramid_ultimate_beast بتبدأ هنا ---


async def pyramid_ultimate_beast(url, name, task_id=None, meta_data=None):
    # 1. تحديد المسار باحترافية (كشف التزييف)
    try:
        BASE_PATH = "/content"
    except ImportError:
        # إذا فشل الاستيراد، فهذا يعني أننا لسنا في كولاب
        BASE_PATH = (
            "/kaggle/working" if os.path.exists("/kaggle/working") else os.getcwd()
        )

    # 1. تحديد المسار الجذري الحقيقي للمشروع
    current_root = os.getcwd()
    # إذا كان المسار الحالي ينتهي بـ "project" بالفعل، لا تضفه مرة أخرى
    if current_root.endswith("project"):
        BASE_DIR = current_root
    else:
        BASE_DIR = os.path.join(current_root, "project")

    # 2. التأكد من إنشاء المجلد والدخول إليه "بذكاء"
    os.makedirs(BASE_DIR, exist_ok=True)
    if os.getcwd() != BASE_DIR:
        os.chdir(BASE_DIR)

    # --- 🟢 تجهيز اللوجو (مرة واحدة لكل عملية) ---
    # مجلد خاص للأدوات الثابتة (اللوجو) بعيد عن مجلد العمليات
    TOOLS_DIR = os.path.join(BASE_PATH, "tools")
    os.makedirs(TOOLS_DIR, exist_ok=True)

    LOGO_URL = "https://res.cloudinary.com/dbahqgo8j/image/upload/q_auto,f_auto,w_80,h_80,c_fill,r_max/blogger/logo.webp"
    LOGO_FILE = os.path.join(TOOLS_DIR, "watermark.webp")  # تغيير المسار لـ TOOLS_DIR

    if not os.path.exists(LOGO_FILE):
        try:

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

    # تأمين الاستدعاء ومنع أي محاولة لاستقبال قيم
    try:
        await ensure_dependencies()
    except Exception as deps_err:
        log.warning(f"⚠️ فشل فحص الأدوات (تجاوز): {deps_err}")
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
        # تأمين Unpacking لمنع خطأ NoneType
        clean_res = get_clean_media_data(original_task_name)
        if clean_res and len(clean_res) == 4:
            search_query_clean, _, _, _ = clean_res
        else:
            search_query_clean = original_task_name

    log.info(
        f"🔎 البحث عن: {search_query_clean} "
        + (f"({extracted_year})" if extracted_year else "")
        + " ..."
    )
    log.info(f"DEBUG: calling get_clean_media_data with {original_task_name}")

    # 2. استدعاء بيانات TMDB مع تأمين الـ Unpacking لمنع خطأ الـ NoneType
    movie_result = get_movie_data(
        search_query_clean if search_query_clean else name, year=extracted_year
    )
    log.info(f"DEBUG: get_movie_data returned: {movie_result}")

    # تأمين الاستخراج لمنع الانهيار حتى لو رجعت بيانات ناقصة أو غلط
    if isinstance(movie_result, (list, tuple)) and len(movie_result) >= 9:
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
        ) = movie_result[
            :9
        ]  # بناخد أول 9 بس للأمان
    else:
        log.warning(
            f"⚠️ بيانات TMDB ناقصة أو غير صالحة لـ {search_query_clean}، سيتم استخدام الافتراضي."
        )
        tmdb_id_fetched, display_title_tmdb, meta_story, final_poster = (
            None,
            original_task_name,
            "",
            "",
        )
        meta_labels, meta_duration, meta_rating, meta_runtime, meta_year = (
            [],
            "",
            "0",
            0,
            extracted_year or "2026",
        )
    log.info(f"DEBUG: Final media data - Title: {display_title}, Year: {meta_year}")
    # دمج الاسم المجلوب مع تفاصيل الحلقة من التاسك الأصلي
    display_title = display_title_tmdb if display_title_tmdb else original_task_name

    # التأكد من بقاء معلومات الموسم والحلقة في العنوان المعروض
    if "الموسم" in original_task_name and "الموسم" not in display_title:
        season_match = re.search(r"(الموسم\s*\d+)", original_task_name)
        if season_match:
            display_title = display_title + " " + season_match.group(1)

    if "الحلقة" in original_task_name and "الحلقة" not in display_title:
        # استخراج "الحلقة X" وإضافتها
        ep_match = re.search(r"(الحلقة\s*\d+|ح\s*\d+)", original_task_name)
        if ep_match:
            display_title = display_title + " " + ep_match.group(1)

    # --- 2. نظام منع التكرار الاحترافي (Supabase) ---
    # 1. استخراج البيانات النظيفة فوراً قبل أي فحص
    clean_res_db = get_clean_media_data(display_title)
    if clean_res_db and len(clean_res_db) == 4:
        clean_title_search, category_search, current_season_no, current_ep_no = (
            clean_res_db
        )
    else:
        clean_title_search, category_search, current_season_no, current_ep_no = (
            display_title,
            "movie",
            None,
            None,
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
    # استدعاء الحفظ الأولي
    save_res = save_to_supabase(
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

    # التأمين النهائي
    if save_res and len(save_res) == 4:
        e_id, media_id, meta_story, final_poster = save_res
    else:
        # لو فشل الحفظ، نوقف المهمة بشياكة بدل ما السكربت ينهار
        log.error("❌ فشل الحفظ الأولي في قاعدة البيانات (save_to_supabase رجعت None)")
        return

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

    # 2. معالجة روابط MixDrop
    elif "mixdrop" in url:
        log.info("🎯 تم اكتشاف رابط MixDrop.. جاري الصيد من صفحة التحميل...")
        direct_link = await get_mixdrop_direct_link(url)
        if direct_link == "404_DELETED":
            # رمي خطأ صريح لتشغيل نظام تنظيف الميديا (الذي أعددناه سابقاً)
            raise Exception("الملف محذوف نهائياً من المصدر (MixDrop 404)")

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
        "-v",
        "--no-playlist",
        "--geo-bypass",
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
            "--newline",
            f"{url}",
            "-o",
            download_path_template,
        ]
    )

    # --- 🟢 منطق التحميل والتعامل الذكي (Async الكامل - الحل الجذري) ---
    if not is_local_file:
        log.info(f"🌐 رابط ويب، جاري التحميل بنظام Async Subprocess...")

        # استخدام asyncio لضمان السيطرة الكاملة على العملية
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
        )

        last_db_update = 0
        last_percent_log = -1  # <--- ضيف السطر ده هنا

        # قراءة المخرجات واستخراج البيانات الكاملة
        # قراءة المخرجات واستخراج البيانات الكاملة
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            line_str = line.decode().strip()

            # Regex شامل يصيد النسبة، الحجم، السرعة، والوقت المتبقي بدقة
            progress_match = re.search(
                r"\[download\]\s+(\d+\.\d+)%\s+of\s+([\d\w\.]+)(?:\s+at\s+([\d\w\./s]+))?(?:\s+ETA\s+([\d:]+))?",
                line_str,
            )

            if progress_match:
                percent = progress_match.group(1)
                total = progress_match.group(2)
                speed = progress_match.group(3) or "---"
                eta = progress_match.group(4) or "--:--"
                percent_int = int(float(percent))

                # --- التعديل لضمان الظهور في لوجات Hugging Face ---
                # بدلاً من sys.stdout، سنستخدم print عادية لكن بشرط النسبة
                # سنطبع فقط عند كل 5% أو كل 10 ثواني عشان اللوج ميتمليش
                now = time.time()
                if percent_int % 5 == 0 and percent_int != last_percent_log:
                    # هذه ستظهر كسطر جديد ومنظم كل 5%
                    log.info(
                        f"📥 {display_title[:15]}.. | {percent_int}% of {total} | ⚡ {speed} | ⏳ ETA: {eta}"
                    )
                    last_percent_log = percent_int

                # لتحديث الـ UI الخاص بـ Supabase (بدون طباعة)
                if task_id and (now - last_db_update > 15):
                    try:
                        supabase.table("download_tasks").update(
                            {
                                "progress_percent": percent_int,
                                "status_message": f"📥 جاري التحميل: {percent_int}%",
                                "download_speed": speed,
                            }
                        ).eq("id", task_id).execute()
                        last_db_update = now
                    except:
                        pass
            # 3. طباعة الأخطاء الحقيقية فقط في سطر جديد
            elif any(x in line_str.upper() for x in ["ERROR", "WARNING", "FAILED"]):
                print(
                    f"\n⚠️ ALERT_LOG: {line_str}"
                )  # استخدم \n عشان ميمسحش شريط التحميل

        # سطر جديد بعد انتهاء اللوب عشان اللوجات اللي بعدها متجيش جنب الشريط
        print("")

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

                def get_duration(file):
                    cmd = [
                        "ffprobe",
                        "-v",
                        "error",
                        "-show_entries",
                        "format=duration",
                        "-of",
                        "default=noprint_wrappers=1:nokey=1",
                        file,
                    ]
                    result = subprocess.run(
                        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                    )
                    return (
                        float(result.stdout.strip()) if result.stdout.strip() else 0.0
                    )

                # تجهيز النص العربي
                raw_text = "To see more, please search on Google for EGY PYRAMID"
                reshaped_text = arabic_reshaper.reshape(raw_text)
                bidi_text = get_display(reshaped_text)  # النص الآن جاهز للعرض الصحيح

                duration = get_duration(vid_path)
                mid_time = duration / 2

                # تجهيز النص العربي
                raw_text = "To see more, please search on Google for EGY PYRAMID"
                reshaped_text = arabic_reshaper.reshape(raw_text)
                bidi_text = get_display(reshaped_text)  # النص الآن جاهز للعرض الصحيح

                duration = get_duration(vid_path)
                mid_time = duration / 2

                # ثانياً: أمر FFmpeg المطور مع إضافة -loglevel error لكتم اللوجات
                ffmpeg_cmd = (
                    f'ffmpeg -loglevel error -y -i "{vid_path}" -i "{LOGO_FILE}" -filter_complex '
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

            if category_search == "tv":
                # 1. استدعاء آمن للدالة وتخزينها في متغير وسيط
                clean_res_loop = get_clean_media_data(loop_display_title)

                # 2. التحقق من النتيجة قبل فك التغليف (Unpacking)
                if clean_res_loop and len(clean_res_loop) == 4:
                    c_title_l, c_cat_l, c_season_l, c_ep_l = clean_res_loop

                    # 3. محاولة البحث في قاعدة البيانات (حطينا الـ try هنا بس لجزء الداتابيز)
                    try:
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
                            s_query = (
                                supabase.table("seasons")
                                .select("id")
                                .eq("media_id", m_id_l)
                                .eq("season_number", c_season_l)
                                .execute()
                            )
                            if s_query.data:
                                s_id_l = s_query.data[0]["id"]
                                e_query = (
                                    supabase.table("episodes")
                                    .select("id")
                                    .eq("media_id", m_id_l)
                                    .eq("season_id", s_id_l)
                                    .eq("episode_number", c_ep_l)
                                    .execute()
                                )
                                if e_query.data:
                                    ep_id_found = e_query.data[0]["id"]
                                    links_query = (
                                        supabase.table("links")
                                        .select("id")
                                        .eq("episode_id", ep_id_found)
                                        .execute()
                                    )
                                    if links_query.data:
                                        log.info(
                                            f"✅ [تخطي]: الحلقة {c_ep_l} من الموسم {c_season_l} موجودة ولها روابط!"
                                        )
                                        continue
                                    else:
                                        log.info(
                                            f"🔄 [تحديث]: الحلقة {c_ep_l} موجودة بدون روابط..."
                                        )
                    except Exception as e:
                        log.warning(f"⚠️ فشل فحص تكرار الحلقة في الداتابيز: {e}")
                else:
                    log.warning(
                        f"⚠️ فشل تنظيف بيانات الحلقة {loop_display_title} - سيتم تجاوز فحص التكرار"
                    )

            # لاحظ أن السطور التالية خارج الـ if ومرتبة معها في نفس المستوى
            file_name = f"{clean_name}.mp4"
            episode_label = f"{loop_display_title}"

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
            # archive_url = "Failed_Archive_Upload"
            archive_url = "Disabled"  # تغيير القيمة الافتراضية
            final_file_name = f"f_{media_id}_{e_id}_{idx}.mp4"

            try:
                pass  # إضافة pass لتجاوز هذا الجزء تماماً
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

            # try:

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
