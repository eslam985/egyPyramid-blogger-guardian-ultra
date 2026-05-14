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


def apply_media_disguise(vid_path, idx, display_title, LOGO_FILE):
    """
    تقوم هذه الدالة بتطبيق فلتر FFmpeg لكسر بصمة الفيديو وإضافة الشعارات.
    """
    try:
        # إنشاء مسار للملف المموه في نفس مجلد الفيديو الحالي
        extract_dir_current = os.path.dirname(vid_path)
        disguised_file = os.path.join(extract_dir_current, f"disguised_{idx}.mp4")

        log.info(f"🕵️ جاري تطبيق التمويه لكسر البصمة: {os.path.basename(vid_path)}")

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
            return float(result.stdout.strip()) if result.stdout.strip() else 0.0

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

        # 1. حساب المدة والتحكم الديناميكي في الجودة والمساحة
        duration = get_duration(vid_path)
        mid_time = duration / 2
        duration_mins = duration / 60

        if duration_mins > 150:
            # إعدادات للأفلام الطويلة جداً (أمان ضد التقسيم)
            t_maxrate, t_bufsize, t_crf = "1.5M", "1.5M", 28
            log.info(f"🎬 فيلم طويل ({duration_mins:.1f}m) -> ضبط: 1.5M/CRF28")
        else:
            # إعدادات للأفلام العادية (أعلى جودة ممكنة)
            t_maxrate, t_bufsize, t_crf = "1.8M", "3M", 26
            log.info(f"🎬 فيلم عادي ({duration_mins:.1f}m) -> ضبط: 1.8M/CRF26")

        # 2. بناء أمر FFmpeg بالقيم الجديدة
        ffmpeg_cmd = (
            f'ffmpeg -loglevel error -y -i "{vid_path}" -i "{LOGO_FILE}" -filter_complex '
            f'"[0:v]scale=iw*1.05:-1,crop=iw/1.05:ih/1.05,eq=gamma=1.05:contrast=1.03[v_final]; '
            f"[v_final]drawtext=text='EGY PYRAMID':fontcolor=0xFFD700:fontsize=80:x=(w-text_w)/2:y=(h-text_h)/2:enable='between(t,0,10)'[txt1]; "
            f"[txt1]drawtext=text='{bidi_text}':fontfile=/content/arial.ttf:fontcolor=0xFFD700:fontsize=w/35:x=(w-text_w)/2:y=h-th-40:"
            f"enable='between(t,{mid_time},{mid_time+10})'[txt2]; "
            f"[1:v]format=rgba,colorchannelmixer=aa=1.0[logo_bright]; "
            f"[txt2][logo_bright]overlay=W-w-20:20[outv]"
            f'" '
            f'-map "[outv]" -map 0:a '
            f"-c:v libx264 -preset superfast -crf {t_crf} "
            f"-maxrate {t_maxrate} -bufsize {t_bufsize} -threads 0 -pix_fmt yuv420p "
            f'-c:a aac -b:a 128k -ar 44100 "{disguised_file}"'
        )

        # تنفيذ العملية
        subprocess.run(ffmpeg_cmd, shell=True, check=True)

        # الاستبدال المادي: حذف الأصلي وتسمية المموه باسم الأصلي
        if os.path.exists(disguised_file):
            os.remove(vid_path)
            os.rename(disguised_file, vid_path)
            log.info(f"✅ تم تحصين الحلقة {idx} بنجاح!")

    except Exception as e:
        log.warning(f"⚠️ خطأ في التمويه، سيتم الرفع الأصلي: {e}")


def Upload_To_Archive(
    vid_path,
    media_id,
    e_id,
    idx,
    identifier,
    final_file_name,
    ARCHIVE_ACCESS_KEY,
    ARCHIVE_SECRET_KEY,
    task_id=None,
):
    """
    تقوم هذه الدالة برفع نسخة احتياطية من الملف الخام إلى Archive.org وتحديث روابط سوبابيز.
    """
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

        pbar_archive = tqdm_std(
            total=os.path.getsize(vid_path),
            desc=f"☁️ أرشيف (كامل)",
            unit="B",
            unit_scale=True,
            mininterval=3.0,  # تحديث كل 3 ثوانٍ فقط (مثالي للسرعات البطيئة في كولاب)
            maxinterval=10.0,
            ascii=" █",  # استبدال الهاشتاج بمربعات ناعمة
            colour="green",  # اختيار لون الشريط (يعمل في كولاب)
        )

        # اسم ملف مشفر تماماً
        # 1. إنشاء الـ stream وربطه بملف الفيديو
        stream = ProgressStream(vid_path, pbar_archive, episode_id=e_id)
        # 2. تمرير الـ stream مباشرة لمكتبة الرفع
        # الـ stream الآن هو "المخبر" الذي يخبر pbar بكل بايت يخرج

        try:
            # التصحيح هنا: استدعاء upload من المكتبة وليس اسم دالتك الحالية
            from internetarchive import upload

            upload(
                identifier,
                files={
                    final_file_name: stream
                },  # 👈 التعديل هنا: استخدم stream وليس f_data
                # إخفاء اسم الفيلم من البيانات الوصفية (Metadata)
                metadata={
                    "title": f"M-{media_id}-E{e_id}",
                    "mediatype": "movies",
                    "description": f"Internal ID: {media_id}_{e_id}_{idx}",
                },
                access_key=ARCHIVE_ACCESS_KEY,
                secret_key=ARCHIVE_SECRET_KEY,
                verbose=False,
            )
        finally:
            stream.close()
            pbar_archive.close()
        direct_download_url = (
            f"https://archive.org/download/{identifier}/{final_file_name}"
        )

        # حقن الرابط في سوبابيز
        supabase.table("links").insert(
            {
                "episode_id": e_id,
                "url": direct_download_url,
                "server_name": "archive",
                "last_check_status": "valid",
            }
        ).execute()

        log.info(f"✅ تم الأرشفة بنجاح: {direct_download_url}")
        return direct_download_url  # مهم جداً للـ Loop

    except Exception as e:
        log.error(f"❌ خطأ أرشيف: {e}")
        return "Failed_Archive_Upload"


# =====================================================================
# الدوال الجديدة المساعدة (Helper Functions)
# =====================================================================

def setup_workspace() -> dict:
    """
    تجهيز بيئة العمل: تحديد المسارات، إنشاء المجلدات، تحميل اللوجو، تغيير الدليل.
    تعيد قاموساً يحتوي على BASE_PATH, BASE_DIR, TOOLS_DIR, LOGO_FILE.
    """
    try:
        BASE_PATH = "/content"
    except ImportError:
        BASE_PATH = (
            "/kaggle/working" if os.path.exists("/kaggle/working") else os.getcwd()
        )

    current_root = os.getcwd()
    if current_root.endswith("project"):
        BASE_DIR = current_root
    else:
        BASE_DIR = os.path.join(current_root, "project")

    os.makedirs(BASE_DIR, exist_ok=True)
    if os.getcwd() != BASE_DIR:
        os.chdir(BASE_DIR)

    TOOLS_DIR = os.path.join(BASE_PATH, "tools")
    os.makedirs(TOOLS_DIR, exist_ok=True)

    LOGO_URL = "https://res.cloudinary.com/dbahqgo8j/image/upload/q_auto,f_auto,w_80,h_80,c_fill,r_max/blogger/logo.webp"
    LOGO_FILE = os.path.join(TOOLS_DIR, "watermark.webp")

    if not os.path.exists(LOGO_FILE):
        try:
            with httpx.Client(follow_redirects=True) as client:
                resp = client.get(LOGO_URL)
                with open(LOGO_FILE, "wb") as f:
                    f.write(resp.content)
            log.info("✅ اللوجو جاهز ومؤمن في مجلد الأدوات.")
        except:
            pass

    log.info(f"🛠️ مسار العمل الحالي للوحش: {os.getcwd()}")

    return {
        "BASE_PATH": BASE_PATH,
        "BASE_DIR": BASE_DIR,
        "TOOLS_DIR": TOOLS_DIR,
        "LOGO_FILE": LOGO_FILE,
    }


def extract_clean_media_info(raw_name: str) -> tuple:
    """
    تنظيف اسم الميديا واستخراج السنة منه.
    تعيد (clean_name, extracted_year).
    تتعامل مع روابط topcinema.rip.
    """
    if "topcinema.rip" in str(raw_name):
        decoded = unquote(str(raw_name))
        match = re.search(r"فيلم-(.*?)-مترجم", decoded)
        raw_name = (
            match.group(1).replace("-", " ").title()
            if match
            else decoded.split("/")[-2].replace("-", " ").replace("فيلم", "").title()
        )

    original_task_name = str(raw_name).strip()
    year_match = re.search(r"\b((?:19|20)\d{2})\b", original_task_name)
    extracted_year = year_match.group(1) if year_match else None

    return original_task_name, extracted_year


def fetch_tmdb_metadata(search_query: str, year=None) -> dict:
    """
    جلب بيانات الميديا من TMDB/IMDB.
    تعيد قاموساً بالمفاتيح: tmdb_id, display_title, story, poster, labels,
    duration, rating, runtime, year.
    في حالة فشل أو نقص البيانات، تعيد قيماً افتراضية.
    """
    log.info(f"🔍 جلب بيانات العمل من TMDB/IMDB للتحقق من الأرشيف...")
    log.info(
        f"🔎 البحث عن: {search_query} "
        + (f"({year})" if year else "")
        + " ..."
    )
    log.info(f"DEBUG: calling get_movie_data with {search_query}")

    movie_result = get_movie_data(search_query, year=year)
    log.info(f"DEBUG: get_movie_data returned: {movie_result}")

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
        ) = movie_result[:9]
    else:
        log.warning(
            f"⚠️ بيانات TMDB ناقصة أو غير صالحة لـ {search_query}، سيتم استخدام الافتراضي."
        )
        tmdb_id_fetched, display_title_tmdb, meta_story, final_poster = (
            None,
            search_query,
            "",
            "",
        )
        meta_labels, meta_duration, meta_rating, meta_runtime, meta_year = (
            [],
            "",
            "0",
            0,
            year or "2026",
        )

    return {
        "tmdb_id": tmdb_id_fetched,
        "display_title": display_title_tmdb,
        "story": meta_story,
        "poster": final_poster,
        "labels": meta_labels,
        "duration": meta_duration,
        "rating": meta_rating,
        "runtime": meta_runtime,
        "year": meta_year,
    }


def build_display_title(original_task_name: str, tmdb_title: str, season_ep_info=None) -> str:
    """
    بناء الاسم المعروض النهائي مع إضافة معلومات الموسم والحلقة إذا وُجدت.
    season_ep_info: قاموس اختياري يحتوي على season و/أو episode.
    """
    display_title = tmdb_title if tmdb_title else original_task_name

    if "الموسم" in original_task_name and "الموسم" not in display_title:
        season_match = re.search(r"(الموسم\s*\d+)", original_task_name)
        if season_match:
            display_title = display_title + " " + season_match.group(1)

    if "الحلقة" in original_task_name and "الحلقة" not in display_title:
        ep_match = re.search(r"(الحلقة\s*\d+|ح\s*\d+)", original_task_name)
        if ep_match:
            display_title = display_title + " " + ep_match.group(1)

    if season_ep_info:
        season = season_ep_info.get("season")
        episode = season_ep_info.get("episode")
        if season and "الموسم" not in display_title:
            display_title = f"{display_title} الموسم {season}"
        if episode and "الحلقة" not in display_title:
            display_title = f"{display_title} الحلقة {episode}"

    return display_title


def check_media_duplicate(clean_title: str, year: str, category: str, season_no, ep_no) -> dict:
    """
    التحقق من وجود الميديا/الحلقة مسبقاً في Supabase.
    تعيد قاموساً بالمفاتيح: exists (bool), media_id (int|None), episode_id (int|None).
    """
    result = {"exists": False, "media_id": None, "episode_id": None}
    try:
        media_id = None
        # الخطوة 1: البحث المباشر
        m_query = (
            supabase.table("medias")
            .select("id, title")
            .eq("title", clean_title)
            .eq("year", year)
            .execute()
        )

        if m_query.data:
            media_id = m_query.data[0]["id"]
        else:
            # الخطوة 2: البحث الذكي بالاسم المنظف
            search_results = (
                supabase.table("medias")
                .select("id, title")
                .ilike("title", f"%{clean_title}%")
                .execute()
            )
            for row in search_results.data:
                if normalize_title(row["title"]) == clean_title:
                    media_id = row["id"]
                    break

        result["media_id"] = media_id

        if media_id:
            if category == "movie":
                ep_query = (
                    supabase.table("episodes")
                    .select("id")
                    .eq("media_id", media_id)
                    .execute()
                )
                if ep_query.data:
                    result["exists"] = True
                    result["episode_id"] = ep_query.data[0]["id"]
            elif category == "tv" and season_no is not None and ep_no is not None:
                s_query = (
                    supabase.table("seasons")
                    .select("id")
                    .eq("media_id", media_id)
                    .eq("season_number", season_no)
                    .execute()
                )
                if s_query.data:
                    s_id = s_query.data[0]["id"]
                    e_query = (
                        supabase.table("episodes")
                        .select("id")
                        .eq("media_id", media_id)
                        .eq("season_id", s_id)
                        .eq("episode_number", ep_no)
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
                            result["exists"] = True
                            result["episode_id"] = ep_id_found

    except Exception as e:
        log.warning(f"⚠️ فشل فحص التكرار: {e}")

    return result


def initialize_supabase_record(display_title: str, original_task_name: str, tmdb_data: dict, temp_id: str) -> tuple:
    """
    إنشاء سجل أولي في Supabase.
    تعيد (e_id, media_id, meta_story, final_poster).
    إذا فشل الحفظ، تسجل خطأ وتعيد (None, None, "", "").
    """
    save_res = save_to_supabase(
        None,
        None,
        "Pending",
        display_title,
        original_task_name,
        tmdb_data["story"],
        tmdb_data["poster"],
        tmdb_data["year"],
        tmdb_data["rating"],
        temp_id,
        "Pending",
        tmdb_id=tmdb_data["tmdb_id"],
        labels=tmdb_data["labels"],
        runtime=tmdb_data["runtime"],
        duration_iso=tmdb_data["duration"],
    )

    if save_res and len(save_res) == 4:
        e_id, media_id, meta_story, final_poster = save_res
        return e_id, media_id, meta_story, final_poster
    else:
        log.error("❌ فشل الحفظ الأولي في قاعدة البيانات (save_to_supabase رجعت None)")
        return None, None, "", ""


async def resolve_direct_url(raw_url: str) -> str:
    """
    معالجة روابط vidtube/lulu/mixdrop واستخراج الرابط المباشر.
    في حالة mixdrop 404، يرمي Exception.
    تعيد الرابط المباشر أو الرابط الأصلي إذا فشلت المعالجة.
    """
    if "vidtube.one" in raw_url or "cdn-tube" in raw_url:
        log.info("🎯 تم اكتشاف رابط VidTube/Lulu.. جاري استخراج الرابط المباشر...")
        direct_link = await get_direct_link_via_playwright(raw_url)
        if direct_link:
            log.info(f"✅ تم صيد الرابط بنجاح! سيتم التحميل الآن.")
            return direct_link
        else:
            log.warning("⚠️ فشل الصيد، سنحاول بالرابط الأصلي (قد يفشل).")
            return raw_url

    elif "mixdrop" in raw_url:
        log.info("🎯 تم اكتشاف رابط MixDrop.. جاري الصيد من صفحة التحميل...")
        direct_link = await get_mixdrop_direct_link(raw_url)
        if direct_link == "404_DELETED":
            raise Exception("الملف محذوف نهائياً من المصدر (MixDrop 404)")
        if direct_link:
            log.info(f"✅ تم صيد رابط MixDrop المباشر بنجاح.")
            return direct_link
        else:
            log.warning("⚠️ فشل الصيد، سنحاول بالرابط الأصلي (قد يفشل).")
            return raw_url

    return raw_url


def build_ytdlp_command(url: str, output_template: str, smart_headers: list) -> list:
    """
    بناء قائمة أوامر yt-dlp الكاملة مع كل الخيارات.
    تعيد القائمة الجاهزة لـ asyncio.create_subprocess_exec.
    """
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

    if "lulu" in url:
        cmd.extend(["--referer", "https://topcinemaa.com/"])

    if "vidtube" in url or "cdn-tube" in url:
        cmd.extend(["--extractor-args", "jwplayer:base-url=https://vidtube.one/"])

    cmd.extend(
        [
            "-f",
            "(bestvideo[width<=720][height<=1280]/bestvideo[height<=720][width<=1280]+bestaudio/best[width<=720][height<=1280]/best[height<=720][width<=1280]) / "
            "(bestvideo[width<=1080][height<=1920][filesize<1950M]+bestaudio/best[width<=1080][height<=1920][filesize<1950M]) / "
            "best",
            "--merge-output-format",
            "mp4",
            "--max-filesize",
            "1950M",
            "--post-overwrites",
            "--no-check-certificate",
            "--newline",
            f"{url}",
            "-o",
            output_template,
        ]
    )

    return cmd


async def download_video(cmd: list, task_id, display_title: str, extract_dir: str):
    """
    تنفيذ عملية التحميل باستخدام asyncio، مع تتبع التقدم وتحديث قاعدة البيانات كل 15 ثانية.
    تعيد المسار الكامل للملف المحمّل، أو None إذا فشل.
    """
    process = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
    )

    last_db_update = 0
    last_percent_log = -1

    while True:
        line = await process.stdout.readline()
        if not line:
            break
        line_str = line.decode().strip()

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
            now = time.time()
            if percent_int % 5 == 0 and percent_int != last_percent_log:
                log.info(
                    f"📥 {display_title[:15]}.. | {percent_int}% of {total} | ⚡ {speed} | ⏳ ETA: {eta}"
                )
                last_percent_log = percent_int

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
        elif any(x in line_str.upper() for x in ["ERROR", "WARNING", "FAILED"]):
            print(f"\n⚠️ ALERT_LOG: {line_str}")

    print("")
    await process.wait()

    if process.returncode != 0:
        if (
            extract_dir
            and os.path.exists(extract_dir)
            and any(
                os.path.isfile(os.path.join(extract_dir, f))
                for f in os.listdir(extract_dir)
            )
        ):
            log.info(
                f"✅ تم تجاوز خطأ المحرك (Code: {process.returncode}) - الملفات موجودة."
            )
        else:
            log.error(f"❌ فشل محرك التحميل! كود الخطأ: {process.returncode}")

    await asyncio.sleep(5)
    actual_downloaded_path = None
    
    search_locations = [extract_dir, os.getcwd()]

    for loc in search_locations:
        if not os.path.exists(loc):
            continue

        all_files = [os.path.join(loc, f) for f in os.listdir(loc)]
        actual_files = [
            f
            for f in all_files
            if os.path.isfile(f)
            and not f.endswith((".part", ".ytdl", ".temp", ".txt", ".md"))
        ]

        if actual_files:
            actual_files.sort(key=os.path.getmtime, reverse=True)
            actual_downloaded_path = actual_files[0]
            break

    if actual_downloaded_path:
        log.info(f"✅ تم اكتمال التحميل الفعلي: {actual_downloaded_path}")
    else:
        log.error(
            f"❌ فشل التحميل: المجلد فارغ! المحتوى الموجود: {os.listdir(extract_dir) if os.path.exists(extract_dir) else 'المجلد غير موجود'}"
        )

    return actual_downloaded_path


def rename_and_move_to_stream(file_path: str, media_id: int, episode_id: int, idx: int) -> tuple:
    """
    إعادة تسمية الملف بالمعرفات الرقمية ونقله لمجلد stream.
    تعيد (final_public_path, direct_remote_url).
    """
    file_extension = os.path.splitext(file_path)[1]
    new_file_name = f"f_{media_id}_{episode_id}_{idx}.mp4"
    new_path = os.path.join(os.path.dirname(file_path), new_file_name)

    try:
        os.rename(file_path, new_path)
        file_path = new_path
        log.info(f"🔄 تم إعادة تسمية الملف إلى المعرف الرقمي: {new_file_name}")
    except Exception as rename_err:
        log.error(f"⚠️ فشل إعادة التسمية، سيتم استخدام الاسم الأصلي: {rename_err}")
        new_file_name = os.path.basename(file_path)

    base_root = os.path.dirname(os.getcwd())
    stream_dir = os.path.join(base_root, "stream")
    os.makedirs(stream_dir, exist_ok=True)

    final_public_path = os.path.join(stream_dir, new_file_name)
    try:
        shutil.copy2(file_path, final_public_path)
        if os.path.exists(file_path):
            os.remove(file_path)
        log.info(f"✅ تم تأمين الملف في المسار العام: {final_public_path}")
    except Exception as move_err:
        log.error(f"❌ خطأ في نقل الملف: {move_err}")

    raw_space_id = os.environ.get("SPACE_ID", "eslam315/egypyramid-guardian-ultra")
    space_domain = raw_space_id.replace("/", "-").lower().strip()
    direct_remote_url = f"https://{space_domain}.hf.space/stream/{new_file_name}"

    log.info(f"🔗 [Direct Link] الرابط جاهز للاختبار: {direct_remote_url}")

    return final_public_path, direct_remote_url


def process_archive_upload(video_path: str, media_id: int, episode_id: int, idx: int, task_id) -> str:
    """
    رفع نسخة احتياطية إلى Archive.org.
    تعيد رابط الأرشيف أو "Disabled" أو "Failed_Archive_Upload".
    """
    rand_id = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
    identifier = f"v{rand_id}x{media_id}x{episode_id}x{idx}"
    final_file_name = f"f_{media_id}_{episode_id}_{idx}.mp4"

    # archive_url = Upload_To_Archive(video_path, media_id, episode_id, idx, identifier, final_file_name, ARCHIVE_ACCESS_KEY, ARCHIVE_SECRET_KEY, task_id)
    archive_url = "Disabled"
    return archive_url


async def upload_to_all_servers(
    video_path: str,
    episode_label: str,
    media_id: int,
    episode_id: int,
    remote_source: str,
    task_id,
    final_file_name: str,
) -> dict:
    """
    الرفع المتوازي الخماسي لجميع السيرفرات: VK, Voe, Dood, Streamtape, Lulu.
    تحفظ الروابط الناجحة في Supabase.
    تعيد قاموساً بالمفاتيح: vk_url, voe_watch, voe_download, dood_url, tape_url, lulu_url.
    """
    e_id = episode_id

    if task_id:
        supabase.table("download_tasks").update(
            {
                "status_message": "🚀 ضخ السيرفرات: VK, Voe, Dood, Tape, Lulu",
                "progress_percent": 95,
            }
        ).eq("id", task_id).execute()

    if e_id:
        supabase.table("episodes").update(
            {
                "status_message": "🚀 جاري ضخ الملف لـ VK والرفع المتوازي للبقية...",
                "progress_percent": 90,
            }
        ).eq("id", e_id).execute()

    log.info(f"🚀 البدء في الرفع المتوازي الخماسي (VK + Voe + Dood + Tape + Lulu)...")

    if remote_source:
        task_voe = upload_to_voe_api(video_path, remote_source)
        await asyncio.sleep(15)
        task_dood = upload_to_doodstream(dood_api_key, remote_source, final_file_name)
        await asyncio.sleep(15)
        task_tape = upload_to_streamtape(st_login, st_key, remote_source, final_file_name)
        await asyncio.sleep(15)
        task_lulu = upload_to_lulustream(lu_key, remote_source, final_file_name)
    else:
        task_voe = task_dood = task_tape = task_lulu = asyncio.sleep(0, result=None)

    loop = asyncio.get_event_loop()
    task_vk = loop.run_in_executor(None, upload_to_vk_local, episode_label, video_path)

    vk_result, file_id, d_url, s_url, lu_url = await asyncio.gather(
        task_vk, task_voe, task_dood, task_tape, task_lulu
    )

    vk_url = vk_result if vk_result else "Failed"
    voe_watch = f"https://voe.sx/e/{file_id}" if file_id else "Failed"
    voe_down = f"https://voe.sx/{file_id}/download" if file_id else "Failed"

    # حفظ النتائج في Supabase
    if vk_url != "Failed":
        supabase.table("links").upsert(
            {"episode_id": e_id, "server_name": "vk", "url": vk_url},
            on_conflict="episode_id, server_name",
        ).execute()
        log.info(f"✅ VK Link Saved to Supabase!")
    else:
        log.warning(f"⚠️ VK upload failed or returned empty URL.")

    if file_id:
        log.info(f"✅ Voe Saved! ID: {file_id}")
    else:
        log.warning(f"⚠️ Voe upload failed or returned empty ID.")

    if d_url:
        supabase.table("links").upsert(
            {"episode_id": e_id, "server_name": "doodstream", "url": d_url},
            on_conflict="episode_id, server_name",
        ).execute()
        log.info(f"✅ DoodStream Saved!")
    else:
        log.warning(f"⚠️ DoodStream upload failed or returned empty URL.")

    if s_url:
        supabase.table("links").upsert(
            {"episode_id": e_id, "server_name": "streamtape", "url": s_url},
            on_conflict="episode_id, server_name",
        ).execute()
        log.info(f"✅ Streamtape Saved!")
    else:
        log.warning(f"⚠️ Streamtape upload failed or returned empty URL.")

    if lu_url:
        supabase.table("links").upsert(
            {"episode_id": e_id, "server_name": "lulustream", "url": lu_url},
            on_conflict="episode_id, server_name",
        ).execute()
        log.info(f"✅ LuluStream Saved!")
    else:
        log.warning(f"⚠️ LuluStream upload failed or returned empty URL.")

    return {
        "vk_url": vk_url,
        "voe_watch": voe_watch,
        "voe_download": voe_down,
        "dood_url": d_url,
        "tape_url": s_url,
        "lulu_url": lu_url,
    }


async def finalize_episode(
    episode_id,
    media_id,
    task_id,
    upload_results: dict,
    tmdb_data: dict,
    category: str,
    original_task_name: str,
    loop_display_title: str,
    meta_story: str,
    final_poster: str,
    meta_year: str,
    meta_rating: str,
    meta_labels: list,
    meta_runtime: int,
    meta_duration: str,
    video_path: str,
    archive_url: str,
    url: str,
):
    """
    إنهاء معالجة الحلقة: رفع MixDrop، التحديث النهائي في Supabase،
    التحقق من الجودة، إطلاق الجاهزية، إرسال تليجرام،
    إغلاق التاسك، حذف الملف المحلي، تحديث حالة الحلقة.
    """
    e_id = episode_id
    voe_watch = upload_results.get("voe_watch", "Failed")
    voe_down = upload_results.get("voe_download", "Failed")
    vk_url = upload_results.get("vk_url", "Failed")

    # --- 9. الرفع لـ MixDrop ---
    try:
        if e_id:
            supabase.table("episodes").update(
                {
                    "status_message": "💧 جاري الرفع لـ MixDrop...",
                    "progress_percent": 99,
                }
            ).eq("id", e_id).execute()

        mix_url = await upload_to_mixdrop(video_path, mix_user, mix_key)
        if mix_url:
            supabase.table("links").upsert(
                {"episode_id": e_id, "server_name": "mixdrop", "url": mix_url},
                on_conflict="episode_id, server_name",
            ).execute()
            log.info(f"✅ تم رفع وحفظ رابط MixDrop: {mix_url}")
    except Exception as e:
        log.warning(f"⚠️ فشل MixDrop: {e}")

    # --- 10. التحديث النهائي الشامل ---
    try:
        save_res = save_to_supabase(
            voe_watch, voe_down, vk_url,
            loop_display_title, original_task_name,
            meta_story, final_poster, meta_year, meta_rating,
            video_path, archive_url, tmdb_id=tmdb_data["tmdb_id"],
            labels=meta_labels, runtime=meta_runtime, duration_iso=meta_duration
        )
    except Exception as e:
        log.error(f"❌ فشل التحديث النهائي في سوبابيز: {e}")
        save_res = None

    if save_res:
        e_id, media_id, meta_story, final_poster = save_res
        log.info(f"🏁 تم إغلاق المهمة بنجاح وحفظ كافة البيانات.")

        row_data_for_tg = {
            "title": loop_display_title,
            "story": meta_story if meta_story else "لا يوجد وصف متاح حالياً.",
            "poster_url": final_poster,
            "labels": meta_labels,
            "year": meta_year,
        }

        status = send_to_telegram(
            row=row_data_for_tg,
            content_type=category,
            action_text="المشاهدة",
            post_url=final_poster,
            lang_val="لغة أصلية (مترجم)",
        )

        if status:
            log.info(f"✅ كولاب أرسل تمبلت تليجرام بنجاح")

        quality_pass = False
        has_metadata = False
        if media_id:
            link_check = (
                supabase.table("links")
                .select("id", count="exact")
                .eq("episode_id", e_id)
                .execute()
            )
            links_count = link_check.count if link_check.count is not None else 0

            has_metadata = bool(meta_story and meta_story.strip()) and bool(
                final_poster and final_poster.strip()
            )

            if links_count >= 3:
                quality_pass = True
                if has_metadata:
                    supabase.table("medias").update({"is_ready": True}).eq(
                        "id", media_id
                    ).execute()
                    log.info(
                        f"🚀 تم إطلاق إشارة الجاهزية الكاملة (سيرفرات: {links_count})"
                    )
                else:
                    log.warning(
                        f"🟡 تم الحفظ بنجاح ولكن بدون جاهزية (نقص في الصورة أو الوصف)"
                    )
            else:
                quality_pass = False

        if task_id:
            try:
                if media_id and not quality_pass:
                    supabase.table("medias").delete().eq("id", media_id).execute()
                    log.warning(f"🗑️ تم حذف الميديا لعدم وجود روابط كافية.")
                    final_status, final_msg = "failed", "❌ فشل: السيرفرات أقل من 3"
                else:
                    final_status = "completed"
                    final_msg = "✅ اكتملت بنجاح!" if has_metadata else "⚠️ اكتملت (بدون بيانات وصفية)"

                supabase.table("download_tasks").update({
                    "status": final_status,
                    "progress_percent": 100,
                    "status_message": final_msg,
                }).eq("id", task_id).execute()
                log.info(f"✅ تم إغلاق التاسك {task_id} بحالة: {final_status}")
            except Exception as task_err:
                log.error(f"❌ فشل تحديث حالة التاسك في سوبابيز: {task_err}")
            else:
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

    # تنظيف الملف المحلي
    if os.path.exists(video_path):
        try:
            os.remove(video_path)
            log.info(f"🗑️ تم تنظيف الملف المحلي: {os.path.basename(video_path)}")
        except Exception as e:
            log.warning(f"⚠️ لم يتم مسح الملف المؤقت: {e}")

    # تحديث الحالة النهائية للحلقة
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


def is_compressed(file_path: str) -> bool:
    """فحص إذا كان الملف مضغوطاً باستخدام أمر file."""
    file_info = subprocess.getoutput(f'file "{file_path}"').lower()
    return "rar archive" in file_info or "zip archive" in file_info


def extract_archive(archive_path: str, extract_dir: str) -> None:
    """استخراج ملف مضغوط باستخدام unrar."""
    subprocess.run(
        ["unrar", "e", "-y", archive_path, os.path.join(extract_dir, "")],
        capture_output=True,
    )
    if os.path.exists(archive_path):
        os.remove(archive_path)


def list_videos(directory: str) -> list:
    """
    جرد ملفات الفيديو في مجلد.
    يشمل امتدادات متعددة وملفات حجمها أكبر من 5 ميجا.
    """
    if not os.path.exists(directory):
        return []

    all_contents = os.listdir(directory)
    videos = [
        os.path.join(directory, f)
        for f in all_contents
        if f.lower().endswith((".mp4", ".mkv", ".avi", ".ts", ".mov", ".webm"))
    ]

    if not videos:
        for f in all_contents:
            full_p = os.path.join(directory, f)
            if os.path.isfile(full_p) and os.path.getsize(full_p) > 5 * 1024 * 1024:
                log.info(f"🎯 تم العثور على الفيديو بالحجم وليس الامتداد: {f}")
                videos.append(full_p)

    videos.sort()
    return videos


# =====================================================================
# الدالة الرئيسية المُعاد هيكلتها
# =====================================================================

async def pyramid_ultimate_beast(url, name, task_id=None, meta_data=None):
    # --- 1. تجهيز بيئة العمل ---
    ws = setup_workspace()
    BASE_PATH = ws["BASE_PATH"]
    BASE_DIR = ws["BASE_DIR"]
    TOOLS_DIR = ws["TOOLS_DIR"]
    LOGO_FILE = ws["LOGO_FILE"]

    try:
        await ensure_dependencies()
    except Exception as deps_err:
        log.warning(f"⚠️ فشل فحص الأدوات (تجاوز): {deps_err}")

    timestamp = int(time.time())

    # --- 2. تنظيف الاسم واستخراج السنة ---
    original_task_name, extracted_year = extract_clean_media_info(name)
    display_title = original_task_name

    # --- 3. تحديد query البحث ---
    if "http" in original_task_name or original_task_name.startswith(("tt", "tmdb")):
        search_query_clean = original_task_name
    else:
        clean_res = get_clean_media_data(original_task_name)
        log.info(f"DEBUG: calling get_clean_media_data with {original_task_name}")
        if clean_res and len(clean_res) == 4:
            search_query_clean, _, _, _ = clean_res
        else:
            search_query_clean = original_task_name

    # --- 4. جلب بيانات TMDB ---
    tmdb_data = fetch_tmdb_metadata(
        search_query_clean if search_query_clean else name,
        year=extracted_year,
    )
    log.info(f"DEBUG: Final media data - Title: {tmdb_data['display_title']}, Year: {tmdb_data['year']}")

    # --- 5. بناء الاسم المعروض النهائي ---
    display_title = build_display_title(original_task_name, tmdb_data["display_title"])

    # --- 6. جلب بيانات التنظيف للـ DB ---
    clean_res_db = get_clean_media_data(display_title)
    if clean_res_db and len(clean_res_db) == 4:
        clean_title_search, category_search, current_season_no, current_ep_no = clean_res_db
    else:
        clean_title_search, category_search, current_season_no, current_ep_no = (
            display_title, "movie", None, None,
        )

    # --- 7. فحص التكرار الأولي ---
    try:
        dup_check = check_media_duplicate(
            clean_title_search, tmdb_data["year"], category_search,
            current_season_no, current_ep_no
        )
        if dup_check["exists"] and category_search == "movie":
            log.info(f"✅ [تخطي]: الفيلم '{display_title}' موجود بالفعل!")
            return
    except Exception as e:
        log.warning(f"⚠️ فشل فحص التكرار الأولي: {e}")

    # --- 8. الحجز الأولي في Supabase ---
    temp_id = f"loading_{timestamp}"
    e_id, media_id, meta_story, final_poster = initialize_supabase_record(
        display_title, original_task_name, tmdb_data, temp_id
    )

    if e_id is None and media_id is None:
        return

    if not e_id:
        log.warning("⚠️ فشل الحصول على ID من ساب باز، لن نتمكن من عرض التقدم الحي.")

    # سحب بيانات tmdb للمتغيرات المحلية
    tmdb_id_fetched = tmdb_data["tmdb_id"]
    meta_labels = tmdb_data["labels"]
    meta_duration = tmdb_data["duration"]
    meta_rating = tmdb_data["rating"]
    meta_runtime = tmdb_data["runtime"]
    meta_year = tmdb_data["year"]

    # --- 9. تحديد نوع المصدر (محلي أم رابط) ---
    clean_name = (
        "".join([c for c in display_title if c.isalnum() or c in (" ", ".", "_")])
        .strip()
        .replace(" ", "_")
    )

    is_local_file = os.path.exists(url)
    actual_downloaded_path = None
    extract_dir = os.path.join(BASE_DIR, f"extracted_{timestamp}")
    os.makedirs(extract_dir, exist_ok=True)
    download_path_template = os.path.join(extract_dir, f"temp_dl_{timestamp}.%(ext)s")
    final_direct_url = None
    log.info(f"📡 جاري فحص الرابط وبدء السحب...")

    if is_local_file:
        log.info(f"♻️ اكتشاف ملف محلي: {url} - سيتم تخطي التحميل.")
        actual_downloaded_path = url
        final_public_path, direct_remote_url = rename_and_move_to_stream(actual_downloaded_path, media_id, e_id, 1)
        actual_downloaded_path = final_public_path
        vid_path = final_public_path
        final_direct_url = direct_remote_url   # حفظ الرابط الديناميكي
        class MockProcess:
            returncode = 0
        process = MockProcess()
    else:
        log.info(f"📡 رابط ويب، جاري التجهيز للسحب...")
        log.info(f"   🚀 [Direct Start] الرابط معتمد — جاري التحميل فوراً...")

        # --- 10. حل الرابط المباشر ---
        url = await resolve_direct_url(url)

        # --- 11. بناء أمر yt-dlp ---
        smart_headers = get_smart_headers(url)
        cmd = build_ytdlp_command(url, download_path_template, smart_headers)

        # --- 12. التحميل ---
        actual_downloaded_path = await download_video(cmd, task_id, display_title, extract_dir)

        if actual_downloaded_path:
            final_public_path, direct_remote_url = rename_and_move_to_stream(actual_downloaded_path, media_id, e_id, 1)
            actual_downloaded_path = final_public_path
            vid_path = final_public_path
            final_direct_url = direct_remote_url   # حفظ الرابط الديناميكي
            class MockProcess:
                returncode = 0
            process = MockProcess()
        else:
            # فشل التحميل - تنظيف وخروج
            if media_id:
                try:
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
            return

    # --- 13. تحديث سوبابيز قبل المعالجة ---
    if task_id:
        supabase.table("download_tasks").update(
            {
                "status_message": "⚙️ جاري فحص الملف ومعالجته...",
                "progress_percent": 91,
                "download_speed": "Processing",
            }
        ).eq("id", task_id).execute()

    # --- 14. منطق المعالجة والرفع ---
    if process and process.returncode == 0 and actual_downloaded_path:
        file_info = subprocess.getoutput(f'file "{actual_downloaded_path}"').lower()
        is_rar = "rar archive" in file_info or "zip archive" in file_info

        if is_rar and not is_local_file:
            log.info("🔓 تم اكتشاف ملف مضغوط حقيقي، جاري البدء في فك التجميع...")
        else:
            if is_local_file:
                log.info(f"🎥 معالجة ملف الفيديو المحلي الجاهز: {name}")
            else:
                log.info(f"🎥 تم تحميل فيديو مباشر بنجاح: {name}")

        if is_rar:
            log.info(f"🔓 تم اكتشاف ملف مضغوط حقيقي، جاري فك الضغط...")
            extract_archive(actual_downloaded_path, extract_dir)
        else:
            log.info(f"🎬 تم اكتشاف فيديو، جاري التحضير للرفع...")
            if not os.path.exists(actual_downloaded_path):
                final_video_path = vid_path
            else:
                _, file_extension = os.path.splitext(actual_downloaded_path)
                final_video_path = os.path.join(
                    extract_dir, f"{clean_name}{file_extension}"
                )
                if actual_downloaded_path != final_video_path:
                    shutil.move(actual_downloaded_path, final_video_path)

            videos = [final_video_path]

        # --- 15. جرد الفيديوهات ---
        log.debug(f"DEBUG: الملفات الموجودة في المجلد حالياً: {os.listdir(extract_dir)}")
        videos = list_videos(extract_dir)

        if not videos:
            if "vid_path" in locals() and os.path.exists(vid_path):
                videos = [vid_path]
            else:
                log.error("❌ لم يتم العثور على فيديوهات!")
                return

        # --- 16. لو أكثر من حلقة، فرخ مهام جديدة ---
        if len(videos) > 1:
            log.info(
                f"🎊 كنز! تم اكتشاف {len(videos)} حلقة. جاري إعادة توزيع المهام..."
            )

            new_task_list = []
            for vid in videos:
                v_name = os.path.basename(vid)
                full_task_name = f"{display_title} {v_name}"
                new_task_list.append({"url": vid, "name": full_task_name})

            if task_id:
                supabase.table("download_tasks").update(
                    {
                        "status_message": f"✅ تم تفكيك الملف لـ {len(videos)} حلقة، جاري المعالجة الفردية...",
                        "status": "completed",
                    }
                ).eq("id", task_id).execute()

            await run_pyramid_tasks(new_task_list)

            if os.path.exists(extract_dir):
                shutil.rmtree(extract_dir)
            return

        log.info(f"✅ تم اعتماد البيانات المجلوبة مسبقاً لـ: {display_title}")
        log.info(
            f"✅ تم اكتشاف {len(videos)} ملف. جاري المعالجة والرفع باسم: {display_title}"
        )

        # --- 17. لووب الحلقات ---
        for idx, vid_path in enumerate(videos, 1):
            # apply_media_disguise(vid_path, idx, display_title, LOGO_FILE)
            file_size_gb = os.path.getsize(vid_path) / (1024**3)
            current_file_name = os.path.basename(vid_path)
            if len(videos) > 1:
                loop_display_title = f"{display_title} {current_file_name}"
            else:
                loop_display_title = display_title

            # فحص تكرار الحلقة للمسلسلات
            if category_search == "tv":
                clean_res_loop = get_clean_media_data(loop_display_title)
                if clean_res_loop and len(clean_res_loop) == 4:
                    c_title_l, c_cat_l, c_season_l, c_ep_l = clean_res_loop
                    dup_check = check_media_duplicate(c_title_l, meta_year, "tv", c_season_l, c_ep_l)
                    if dup_check["exists"]:
                        log.info(f"✅ [تخطي]: الحلقة {c_ep_l} من الموسم {c_season_l} موجودة ولها روابط!")
                        continue
                    elif dup_check["media_id"]:
                        log.info(f"🔄 [تحديث]: الحلقة {c_ep_l} موجودة بدون روابط...")
                else:
                    log.warning(f"⚠️ فشل تنظيف بيانات الحلقة {loop_display_title} - سيتم تجاوز فحص التكرار")

            # --- 18. تجهيز المعرفات ---
            episode_label = f"{loop_display_title}"
            rand_id = "".join(
                random.choices(string.ascii_lowercase + string.digits, k=4)
            )
            identifier = f"v{rand_id}x{media_id}x{e_id}x{idx}"
            final_file_name = f"f_{media_id}_{e_id}_{idx}.mp4"

            # --- 19. الأرشفة ---
            log.info(f"📦 أرشفة النسخة الكاملة: {episode_label}")
            archive_url = process_archive_upload(vid_path, media_id, e_id, idx, task_id)
            # --- 20. استخدام الرابط الديناميكي المحفوظ ---
            if final_direct_url:
                log.info(f"🔗 [Direct Link] استخدام الرابط الديناميكي: {final_direct_url}")
            else:
                log.warning("⚠️ الرابط الديناميكي غير متاح، سيتم استخدام الرابط الأصلي")

            if e_id:
                try:
                    supabase.table("episodes").update(
                        {
                            "status_message": "🚀 جاري الضخ للسيرفرات الخماسية عبر الرابط المباشر...",
                            "progress_percent": 85,
                        }
                    ).eq("id", e_id).execute()
                except:
                    pass

            # --- 21. الرفع المتوازي الخماسي ---
            if vid_path and os.path.exists(vid_path):
                if final_direct_url:
                    remote_source = final_direct_url
                    log.info(f"✅ المصدر المعتمد للرفع الخماسي: [Hugging Face Direct Stream]")
                elif archive_url and "archive.org" in archive_url:
                    remote_source = identifier
                    log.info(f"✅ المصدر المعتمد: Archive.org")
                else:
                    remote_source = url
                    log.warning(f"⚠️ الرابط الديناميكي غير متاح، استخدام الرابط الأصلي: {url}")

                log.info(f"📡 القيمة المرسلة لمهام الرفع: {remote_source}")
                await asyncio.sleep(10)

                upload_results = await upload_to_all_servers(
                    vid_path, episode_label, media_id, e_id,
                    remote_source, task_id, final_file_name
                )
            else:
                upload_results = {
                    "vk_url": "Failed", "voe_watch": "Failed",
                    "voe_download": "Failed", "dood_url": None,
                    "tape_url": None, "lulu_url": None,
                }

            # --- 22. الإنهاء والتحديث النهائي ---
            await finalize_episode(
                episode_id=e_id,
                media_id=media_id,
                task_id=task_id,
                upload_results=upload_results,
                tmdb_data=tmdb_data,
                category=category_search,
                original_task_name=original_task_name,
                loop_display_title=loop_display_title,
                meta_story=meta_story,
                final_poster=final_poster,
                meta_year=meta_year,
                meta_rating=meta_rating,
                meta_labels=meta_labels,
                meta_runtime=meta_runtime,
                meta_duration=meta_duration,
                video_path=vid_path,
                archive_url=archive_url,
                url=url,
            )

    # --- خارج لووب الحلقات: مسح المجلد بالكامل ---
    if os.path.exists(extract_dir):
        shutil.rmtree(extract_dir)
    log.info(f"\n✨ المهمة انتهت بنجاح!")