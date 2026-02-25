import os
import time
import re
import shutil
import subprocess
import nest_asyncio
from urllib.parse import unquote

# 1. استيراد النسخة المهذبة من tqdm التي صنعناها في processors
# هذا السطر هو الأهم لضمان ثبات شكل البروجرس بار
from .processors import (
    tqdm,
    tqdm_custom,
    get_clean_media_data,
    get_movie_data,
    upload_to_doodstream,
    upload_to_streamtape,
    upload_to_mixdrop,
    upload_to_voe_api,
    upload_to_vk_local,  # <--- تأكد من إضافة VK هنا
)

# 2. استيراد المحرك
from .engine import *

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
):
    try:
        clean_title, category, actual_ep_no = get_clean_media_data(display_title)
        c_title, c_cat, c_ep = get_clean_media_data(original_task_name)

        media_payload = {
            "tmdb_id": (
                str(meta_data.get("id"))
                if (meta_data and isinstance(meta_data, dict))
                else None
            ),
            "title": c_title,
            "story": meta_story,
            "poster_url": raw_poster,
            "category": c_cat,
            "year": str(meta_year),
            "rating": str(meta_rating),
        }

        # 1. ابحث عن المسلسل أولاً لمنع دهس البيانات (القصة والبوستر)
        existing_media = (
            supabase.table("medias")
            .select("id")
            .eq("title", c_title)
            .eq("year", str(meta_year))
            .execute()
        )

        if existing_media.data:
            # المسلسل موجود، خذ الـ ID فقط ولا تعدل القصة أو البوستر
            m_id = existing_media.data[0]["id"]
        else:
            # المسلسل غير موجود، قم بإنشائه لأول مرة بالبيانات المتاحة
            media_res = supabase.table("medias").insert(media_payload).execute()
            m_id = media_res.data[0]["id"]

        # بناء بيانات الحلقة
        ep_payload = {
            "media_id": m_id,
            "episode_number": actual_ep_no,
            "identifier": identifier,
            "is_synced": False,
        }

        # التعديل هنا: نستخدم 'media_id, episode_number' لمنع التكرار
        # بدلاً من الـ identifier المتقلب
        ep_res = (
            supabase.table("episodes")
            .upsert(ep_payload, on_conflict="media_id, episode_number")
            .execute()
        )
        e_id = ep_res.data[0]["id"]

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
        for entry in link_entries:
            supabase.table("links").upsert(
                entry, on_conflict="episode_id, server_name"
            ).execute()

        # ابحث عن السطر القديم واستبدله بهذا في ملف المحرك
        print(
            f"🚀 [Supabase]: تم مزامنة البيانات بنجاح | الرمز الفريد: {identifier} | العنوان: {display_title}"
        )
        return e_id  # أضف هذا السطر لكي نحصل على الرقم التعريفي
    except Exception as e:
        print(f"❌ خطأ أثناء الحفظ في ساب باز: {e}")
        return None


async def pyramid_ultimate_beast(url, name, task_id=None, meta_data=None):
    # 1. تثبيت المسار القابل للكتابة (الورشة)
    BASE_DIR = "/kaggle/working/project"

    # 2. التأكد من الانتقال إليه فعلياً لضمان أن أي ملف نسبي يُنشأ هناك
    if os.path.exists(BASE_DIR):
        os.chdir(BASE_DIR)

    # 3. طباعة المسار للتأكد في اللوجات (اختياري لل debugging)
    print(f"🛠️ مسار العمل الحالي للوحش: {os.getcwd()}")

    await ensure_dependencies()
    timestamp = int(time.time())

    # ... بقية الكود كما هو ...
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

    (
        display_title,
        meta_story,
        raw_poster,
        meta_labels,
        meta_duration,
        meta_rating,
        meta_runtime,
        meta_year,
    ) = get_movie_data(name)
    # افترضنا أن دالة get_movie_data تعيد الـ ID أيضاً أو القاموس الكامل
    # إذا كانت get_movie_data تعيد بيانات فقط، سنقوم ببناء قاموس وهمي لـ meta_data
    current_meta = {"id": None}  # يمكنك تطوير هذا لاحقاً لجلب الـ ID الحقيقي

    # تعديل جوهري: إذا كان الاسم المجلوب من API لا يشبه اسمك الأصلي، أو جاء بأرقام غريبة، ارجع لاسمك الأصلي
    if (
        not display_title
        or any(char.isdigit() for char in display_title)
        and len(display_title) < 10
    ):
        display_title = original_task_name
        print(f"⚠️ تم استعادة الاسم الأصلي من التاسك لضمان الدقة: {display_title}")

    # تأكد أن display_title لا يضيع منه رقم الحلقة
    if "الحلقة" in original_task_name and "الحلقة" not in display_title:
        display_title = original_task_name

    # --- 2. نظام منع التكرار (البحث في شيت الأرشيف) 🆕 ---
    # معرف شيت الأرشيف الخاص بك الذي أرسلته لي
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
    e_id = save_to_supabase(
        None,
        None,
        "Pending",
        display_title,
        original_task_name,
        meta_story,
        raw_poster,
        meta_year,
        meta_rating,
        temp_id,
        "Pending",
        current_meta,
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

    # التعديل النهائي لتجاوز حماية الـ IP وتزوير هوية المتصفح
    cmd = [
        "yt-dlp",
        "--no-playlist",
        "--concurrent-fragments",
        "5",
        "--user-agent",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "--add-header",
        "Accept: video/webp,video/apng,video/*,*/*;q=0.8",
        "--add-header",
        "Accept-Language: en-US,en;q=0.9,ar;q=0.8",
        "--add-header",
        "Referer: https://vidtube.one/",
        "--add-header",
        "Origin: https://vidtube.one",
        "--no-check-certificate",
        "--socket-timeout",
        "60",
        "-f",
        "best",
        f"{url}",
        "-o",
        download_path_template,
        "--newline",
        "--progress-template",
        "download:[%(progress._percent_str)s]",
    ]

    # أضف -v لإظهار تفاصيل المنع الحقيقية
    cmd.insert(1, "-v")
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
            file_name = os.path.basename(vid_path)
            episode_label = (
                f"{display_title}"
                if len(videos) == 1
                else f"{display_title} - الحلقة {idx}"
            )
            identifier = f"egy_pyr_{timestamp}_e{idx}"

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
                archive_upload(
                    identifier,
                    files={os.path.basename(vid_path): stream},
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

            # 5. الرفع لـ Voe وتحديث الشيت
            # --- 5. الرفع لـ Voe وتحديث الشيت ---
            final_poster = upload_poster_to_cloudinary(raw_poster) if raw_poster else ""
            poster_formula = (
                f'=IMAGE("{final_poster}")' if final_poster else "No Poster"
            )
            archive_url = f"https://archive.org/details/{identifier}"

            # --- تحديث حالة الرفع لـ Voe ---
            if e_id:
                supabase.table("episodes").update(
                    {
                        "status_message": "🚀 جاري الرفع لسيرفر المشاهدة (Voe)...",
                        "progress_percent": 90,  # نثبتها على 90% لأنها مرحلة سريعة وغالباً لا تعطي نسبة
                        "download_speed": "Uploading...",
                    }
                ).eq("id", e_id).execute()

            file_id = upload_to_voe_api(vid_path, identifier)

            voe_watch = f"https://voe.sx/e/{file_id}" if file_id else "Failed"
            voe_down = f"https://voe.sx/{file_id}/download" if file_id else "Failed"

            # --- 7. الرفع لـ DoodStream و Streamtape (عبر الأرشيف) ---
            if identifier:
                # الرفع لـ DoodStream
                try:
                    d_url = await upload_to_doodstream(
                        dood_api_key, identifier, file_name
                    )
                    if d_url:
                        supabase.table("links").upsert(
                            {
                                "episode_id": e_id,
                                "server_name": "doodstream",
                                "url": d_url,
                            },
                            on_conflict="episode_id, server_name",
                        ).execute()
                        print(f"✅ تم حفظ رابط DoodStream")
                except Exception as e:
                    print(f"⚠️ فشل مهمة DoodStream Remote: {e}")

                # الرفع لـ Streamtape (منفصل ومستقل تماماً)
                try:
                    s_url = await upload_to_streamtape(
                        st_login, st_key, identifier, file_name
                    )
                    if s_url:
                        supabase.table("links").upsert(
                            {
                                "episode_id": e_id,
                                "server_name": "streamtape",
                                "url": s_url,
                            },
                            on_conflict="episode_id, server_name",
                        ).execute()
                        print(f"✅ تم حفظ رابط Streamtape")
                except Exception as e:
                    print(f"⚠️ فشل مهمة Streamtape Remote: {e}")

            try:
                save_to_supabase(
                    voe_watch,
                    voe_down,
                    "Pending",
                    display_title,
                    original_task_name,
                    meta_story,
                    raw_poster,
                    meta_year,
                    meta_rating,
                    identifier,
                    archive_url,
                    current_meta,
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
                    raw_poster,
                    meta_year,
                    meta_rating,
                    identifier,
                    archive_url,
                    current_meta,
                )
            except Exception as e:
                print(f"❌ فشل التحديث النهائي في سوبابيز: {e}")

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
