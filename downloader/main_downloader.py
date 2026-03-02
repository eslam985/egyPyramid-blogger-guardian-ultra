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

ARCHIVE_ACCESS_KEY = "ufnS9MloPsaLYXSl"
ARCHIVE_SECRET_KEY = "euu3u0Lm0bcMFyYB"
lu_key = "244676va68ovreoinx1k42"


def save_to_supabase(
    current_voe,
    current_down,
    current_vk,
    display_title,
    original_task_name,
    meta_story,
    raw_poster,
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
        # نستخدم الاسم النظيف المجلوب من API (display_title) لضمان عدم تسجيل روابط
        c_title, c_cat, actual_ep_no = get_clean_media_data(display_title)

        media_payload = {
            "tmdb_id": str(tmdb_id) if tmdb_id else None,
            "title": c_title,
            "story": meta_story,
            "poster_url": raw_poster,
            "category": c_cat,
            "year": str(meta_year),
            "rating": str(meta_rating),
            "labels": labels,  # العمود الجديد
            "runtime": runtime,  # العمود الجديد
            "duration_iso": duration_iso,  # العمود الجديد (الوحش)
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
                if existing_media.data:
                    m_id = existing_media.data[0]["id"]
                    # تحديث البيانات الحالية (لو غيرت الاسم أو البوستر يلحق يغيرهم)
                    supabase.table("medias").update(media_payload).eq(
                        "id", m_id
                    ).execute()
                else:
                    # بفضل تفعيل "Is Unique" في سوبابيز، الـ upsert سيعمل الآن بسلاسة
                    # لو الـ tmdb_id موجود، سيقوم بالتحديث. لو مش موجود، سيقوم بالإدخال.
                    media_res = (
                        supabase.table("medias")
                        .upsert(media_payload, on_conflict="tmdb_id")
                        .execute()
                    )
                    m_id = media_res.data[0]["id"]

                # 2. إنشاء أو تحديث الحلقة (Episode)
                ep_payload = {
                    "media_id": m_id,
                    "episode_number": actual_ep_no,
                    "identifier": identifier,
                    "is_synced": False,
                }
                ep_res = (
                    supabase.table("episodes")
                    .upsert(ep_payload, on_conflict="media_id, episode_number")
                    .execute()
                )
                e_id = ep_res.data[0]["id"]

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

        # 1. بناء القائمة أولاً
        link_entries = []
        if current_voe and current_voe != "Failed":
            link_entries.append(
                {"episode_id": e_id, "server_name": "voe", "url": current_voe}
            )
        if current_vk and current_vk != "Failed" and current_vk != "Pending":
            link_entries.append(
                {"episode_id": e_id, "server_name": "vk", "url": current_vk}
            )
        if archive_url and "Failed" not in archive_url:
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

        # ابحث عن السطر القديم واستبدله بهذا في ملف المحرك
        print(
            f"🚀 [Supabase]: تم مزامنة البيانات بنجاح | الرمز الفريد: {identifier} | العنوان: {display_title}"
        )
        return e_id  # أضف هذا السطر لكي نحصل على الرقم التعريفي
    except Exception as e:
        print(f"❌ خطأ أثناء الحفظ في ساب باز: {e}")
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

    # ابحث عن هذا الجزء (حوالي السطر 200) واستبدله بهذا:
    (
        tmdb_id_fetched,  # القيمة الجديدة
        display_title,
        meta_story,
        final_poster,
        meta_labels,
        meta_duration,
        meta_rating,
        meta_runtime,
        meta_year,
    ) = get_movie_data(name)

    # --- التعديل الجذري لمنع عودة الروابط كأرقام ---
    is_original_a_link = "http" in original_task_name
    
    if not display_title:
        display_title = original_task_name
    
    # لو الاسم المجلوب فيه أرقام وقصير، بس الاسم الأصلي "رابط"، نرفض الاستعادة
    if any(char.isdigit() for char in display_title) and len(display_title) < 10:
        if is_original_a_link:
            print(f"✅ تم الإبقاء على الاسم المجلوب {display_title} لأن البديل رابط مشوه.")
        else:
            display_title = original_task_name
            print(f"⚠️ تم استعادة الاسم الأصلي من التاسك: {display_title}")

    # تأكد أن display_title لا يضيع منه رقم الحلقة
    if "الحلقة" in original_task_name and "الحلقة" not in display_title:
        display_title = original_task_name

    # --- 2. نظام منع التكرار المطور (أفلام + حلقات مسلسلات) ---
    # --- 2. نظام منع التكرار الاحترافي (Supabase) ---
    # 1. استخراج البيانات النظيفة فوراً قبل أي فحص
    clean_title_search, category_search, current_ep_no = get_clean_media_data(
        display_title
    )

    try:
        is_duplicate = False
        # البحث بالاسم النظيف وليس display_title
        query = (
            supabase.table("medias")
            .select("id")
            .eq("title", clean_title_search)
            .eq("year", meta_year)
            .execute()
        )

        if query.data:
            media_id = query.data[0]["id"]
            # الفحص الآن أصبح دقيقاً جداً بناءً على رقم الحلقة المستخرج
            ep_query = (
                supabase.table("episodes")
                .select("id")
                .eq("media_id", media_id)
                .eq("episode_number", current_ep_no)
                .execute()
            )

            if ep_query.data:
                is_duplicate = True

        if is_duplicate:
            print(f"✅ [تخطي]: {display_title} موجود بالفعل في ساب باز!")
            return
        else:
            print(f"🆕 مهمة جديدة: جاري معالجة {display_title} لضخها في ساب باز...")

    except Exception as e:
        print(f"⚠️ تنبيه: فشل فحص ساب باز، سأكمل كعمل جديد. الخطأ: {e}")

        # --- 3. حجز مكان في قاعدة البيانات قبل البدء ---
    # إنشاء identifier مؤقت للتحميل
    temp_id = f"loading_{timestamp}"

    # استدعاء الحفظ الأولي للحصول على e_id
    # استدعاء الحفظ الأولي للحصول على e_id
    e_id = save_to_supabase(
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
        tmdb_id=tmdb_id_fetched,  # إرسال ID
        labels=meta_labels,  # إرسال التصنيفات
        runtime=meta_runtime,  # إرسال مدة العرض
        duration_iso=meta_duration,  # إرسال ISO
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
    # 2. بناء أمر الوحش (نسخة كسر حماية الـ 9% والـ IP Block)
    # 2. بناء أمر الوحش (نسخة كسر حماية الـ IP Block والتمويه الجغرافي)
    # 1. تحديد المصدر (الذي يطلبه السيرفر عادةً)
    # ملاحظة: سنثبت الـ Referer ليظهر كأننا قادمون من مشغل مشهور
    fixed_referer = "https://vidtube.one/"

    # 2. بناء أمر الوحش (النسخة التي كانت تسحب الـ m3u8 بنجاح)
    cmd = [
        "yt-dlp",
        "-v",
        "--no-playlist",
        "--user-agent",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "--add-header",
        "Accept: video/webp,video/apng,video/*,*/*;q=0.8",
        "--add-header",
        "Accept-Language: en-US,en;q=0.9,ar;q=0.8",
        "--add-header",
        f"Referer: {fixed_referer}",
        "--add-header",
        "Origin: https://vidtube.one",
        # --- التعديل لرفع السرعة وضمان الاستمرار ---
        "--concurrent-fragments",
        "13",  # رفع القوة لـ 10 قنوات سحب
        "--file-access-retries",
        "infinite",  # محاولات لا نهائية للوصول للملف
        "--fragment-retries",
        "infinite",  # لو قطعة فشلت يعيدها فوراً
        "--hls-use-mpegts",  # لضمان عدم الانقطاع عند 9%
        # ----------------------------------------
        "--no-check-certificate",
        "--socket-timeout",
        "60",
        # تأكد أن البروكسي معطل (لان الرابط مربوط بـ IP جهازك حالياً)
        # "--proxy", "socks5://127.0.0.1:9050",
        "-f",
        "best",
        f"{url}",
        "-o",
        download_path_template,
        "--newline",
        "--progress-template",
        "download:[%(progress._percent_str)s]",
    ]

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
    pbar_dl.close()

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
            file_name = f"{clean_name}.mp4"
            episode_label = (
                f"{display_title}"
                if len(videos) == 1
                else f"{display_title} - الحلقة {idx}"
            )
            identifier = f"egy_pyr_{timestamp}_e{idx}"
            # --- تعريف مفاتيح السيرفرات (يجب أن تكون هنا داخل اللوب أو الدالة) ---
            dood_api_key = "553856lyhogniqkwh0q9m5"
            st_login = "b4141c9ac5586a160818"
            st_key = "8OmZOAWa2eHora2"

            # 3. الرفع للأرشيف (بالاسم النظيف)
            print(f"📦 أرشفة النسخة الكاملة: {episode_label}")
            archive_url = "Failed_Archive_Upload"  # Initialize with a failure state
            try:
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
            if identifier:
                # تحديث التسمية لتشمل Lulu
                print(
                    f"🚀 البدء في الرفع المتوازي للرباعي (Voe + Dood + Tape + Lulu)..."
                )

                if e_id:
                    supabase.table("episodes").update(
                        {
                            "status_message": "🚀 جاري الرفع المتوازي لـ 4 سيرفرات مشاهدة...",
                            "progress_percent": 90,
                            "download_speed": "Parallel Uploading...",
                        }
                    ).eq("id", e_id).execute()

                # 1. تحضير المهام مع فواصل زمنية (تجنب زحمة الطلبات)
                task_voe = upload_to_voe_api(vid_path, identifier)

                await asyncio.sleep(8)  # تقليل الفجوة قليلاً لتوفير الوقت
                task_dood = upload_to_doodstream(dood_api_key, identifier, file_name)

                await asyncio.sleep(8)
                task_tape = upload_to_streamtape(
                    st_login, st_key, identifier, file_name
                )

                await asyncio.sleep(8)
                task_lulu = upload_to_lulustream(lu_key, identifier, file_name)

                # 2. إطلاق الصواريخ الأربعة معاً
                file_id, d_url, s_url, lu_url = await asyncio.gather(
                    task_voe, task_dood, task_tape, task_lulu
                )

                # --- 6. معالجة النتائج وحفظها ---

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
                save_to_supabase(
                    voe_watch,
                    voe_down,
                    "Pending",
                    display_title,
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

            # 6. الرفع لـ VK (المرحلة الثانية - محلياً لضمان الاستقرار)
            # 6. الرفع لـ VK
            print(f"🚀 جاري نقل النسخة لـ VK...")
            if e_id:
                supabase.table("episodes").update(
                    {
                        "status_message": "🎬 جاري الرفع والمعالجة على VK...",
                        "progress_percent": 95,
                        "download_speed": "Finalizing...",
                    }
                ).eq("id", e_id).execute()
            vk_url = "Failed"
            try:
                vk_result = upload_to_vk_local(episode_label, vid_path)
                if vk_result:
                    vk_url = vk_result
            except Exception as e:
                print(f"⚠️ فشل VK: {e}")

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
                save_to_supabase(
                    voe_watch,
                    voe_down,
                    vk_url,
                    display_title,
                    original_task_name,
                    meta_story,
                    final_poster,
                    meta_year,
                    meta_rating,
                    identifier,
                    archive_url,
                    tmdb_id=tmdb_id_fetched,  # أضف هذا
                    labels=meta_labels,  # أضف هذا
                    runtime=meta_runtime,  # أضف هذا
                    duration_iso=meta_duration,  # أضف هذا
                )
            except Exception as e:
                print(f"❌ فشل التحديث النهائي في سوبابيز: {e}")

            # ابحث عن السطر الذي يقوم بمسح الملف المحلي (os.remove)
            # قبله مباشرة، أضف هذا الجزء:

            try:
                row_data = {
                    "title": display_title,
                    "story": meta_story,
                    "poster_url": final_poster,
                    "labels": meta_labels,
                }

                # التعديل: جعل الإرسال يرجع نتيجة حقيقية
                # التعديل: إرسال رابط حقيقي بدلاً من النص العربي لتجنب رفض تليجرام
                status = send_to_telegram(
                    row=row_data,
                    content_type="MOVIE" if "فيلم" in display_title else "SERIES",
                    action_text="المشاهدة",
                    post_url="https://egy-pyramid-drama.blogspot.com/",  # تم تغيير النص العربي لرابط حقيقي
                    lang_val="مترجم / مدبلج",
                )
                if status:
                    print(f"✅ كولاب أرسل تمبلت الفيسبوك بنجاح.")
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
