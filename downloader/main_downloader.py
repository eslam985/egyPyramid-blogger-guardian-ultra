import os
import time
import asyncio
import re
from supabase import create_client, Client as SupabaseClient
from urllib.parse import unquote

# أضف هذه الاستيرادات في الأعلى فوراً
import shutil
import subprocess

# احذف الأسطر الأربعة الخاصة بالـ imports لـ processors و engine واستبدلها بهذين السطرين فقط:
from .processors import *
from .engine import *
import nest_asyncio
import asyncio

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

        media_res = (
            supabase.table("medias")
            .upsert(media_payload, on_conflict="title,year")
            .execute()
        )
        m_id = media_res.data[0]["id"]

        ep_payload = {
            "media_id": m_id,
            "episode_number": actual_ep_no,
            "identifier": identifier,
            "is_synced": False,
        }
        ep_res = (
            supabase.table("episodes")
            .upsert(ep_payload, on_conflict="identifier")
            .execute()
        )
        e_id = ep_res.data[0]["id"]

        supabase.table("links").delete().eq("episode_id", e_id).execute()

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

        # في نهاية بلوك الـ try داخل دالة save_to_supabase
        if link_entries:
            supabase.table("links").insert(link_entries).execute()

        print(f"🚀 [Supabase]: تم مزامنة البيانات بنجاح لـ {display_title}")
        return e_id  # أضف هذا السطر لكي نحصل على الرقم التعريفي
    except Exception as e:
        print(f"❌ خطأ أثناء الحفظ في ساب باز: {e}")
        return None


async def pyramid_ultimate_beast(url, name, meta_data=None):
    # أضف هذا السطر في بداية الدالة

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
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
    pbar_dl = tqdm(total=100, desc=f"📥 جاري التحميل: {display_title[:20]}", unit="%")

    last_db_update = 0
    last_percent = 0  # أضف هذا السطر هنا
    for line in process.stdout:
        match = re.search(r"(\d+(?:\.\d+)?)%", line)
        if match:
            current_percent = float(match.group(1))
            if current_percent > last_percent:
                pbar_dl.update(current_percent - last_percent)
                last_percent = current_percent

                # تحديث ساب باز كل 3 ثوانٍ بالسرعة والنسبة
                if e_id and (time.time() - last_db_update > 3):
                    # محاولة استخراج السرعة من السطر (تبحث عن نمط مثل 5.2MiB/s)
                    speed_match = re.search(r"(\d+\.?\d+\w+/s)", line)
                    speed_str = (
                        speed_match.group(1) if speed_match else "Downloading..."
                    )

                    supabase.table("episodes").update(
                        {
                            "progress_percent": int(current_percent),
                            "status_message": "📥 جاري تحميل الفيديو من المصدر",
                            "download_speed": speed_str,
                        }
                    ).eq("id", e_id).execute()
                    last_db_update = time.time()

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

            # 4. الرفع لتليجرام (بالاسم النظيف)
            if file_size_gb > 1.9:
                # كود التقسيم
                duration_cmd = f'ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "{vid_path}"'
                total_seconds = float(subprocess.check_output(duration_cmd, shell=True))
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
                os.remove(part1)
                os.remove(part2)
            else:
                # الحقيقة الصارمة: يجب تصفير العداد ليعرف المتصفح أننا بدأنا مرحلة جديدة (تليجرام)
                if e_id:
                    supabase.table("episodes").update({
                        "status_message": "📤 جاري الرفع إلى تليجرام...",
                        "progress_percent": 0 
                    }).eq("id", e_id).execute()
                
                await upload_to_telegram_only(vid_path, episode_label, episode_id=e_id)
                # وفي حالة التقسيم (الجزء الأول والثاني) مرر نفس الـ e_id أيضاً

            # 5. الرفع لـ Voe وتحديث الشيت
            # --- 5. الرفع لـ Voe وتحديث الشيت ---
            final_poster = upload_poster_to_cloudinary(raw_poster) if raw_poster else ""
            poster_formula = (
                f'=IMAGE("{final_poster}")' if final_poster else "No Poster"
            )
            archive_url = f"https://archive.org/details/{identifier}"

            # --- تحديث حالة الرفع لـ Voe ---
            if e_id:
                supabase.table("episodes").update({
                    "status_message": "🚀 جاري الرفع لسيرفر المشاهدة (Voe)...",
                    "progress_percent": 90, # نثبتها على 90% لأنها مرحلة سريعة وغالباً لا تعطي نسبة
                    "download_speed": "Uploading..."
                }).eq("id", e_id).execute()

            file_id = upload_to_voe_api(vid_path, identifier)

            voe_watch = f"https://voe.sx/e/{file_id}" if file_id else "Failed"
            voe_down = f"https://voe.sx/{file_id}/download" if file_id else "Failed"

            # --- التحديث الأول: احفظ رابط Voe فوراً ---
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
                supabase.table("episodes").update({
                    "status_message": "🎬 جاري الرفع والمعالجة على VK...",
                    "progress_percent": 95, 
                    "download_speed": "Finalizing..."
                }).eq("id", e_id).execute()
            vk_url = "Failed"
            try:
                vk_result = upload_to_vk_local(episode_label, vid_path)
                if vk_result:
                    vk_url = vk_result
            except Exception as e:
                print(f"⚠️ فشل VK: {e}")

            # تحديث الشيت بالبيانات الكاملة (Voe + VK)
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
                print(f"❌ فشل تحديث الشيت: {e}")

            # حذف الملف بعد التأكد من انتهاء كل العمليات
            # حذف الملف بعد التأكد من انتهاء كل العمليات
            if os.path.exists(vid_path):
                try:
                    os.remove(vid_path)
                    print(
                        f"🗑️ تم تنظيف الملف المحلي بنجاح: {os.path.basename(vid_path)}"
                    )
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
        # استدعاء المحرك مباشرة لكل مهمة بدلاً من المرور عبر Loop ينتظر
        await pyramid_ultimate_beast(url, name)
    except Exception as e:
        print(f"❌ خطأ كارثي في معالجة '{name}': {e}")
