# /media/es/DDrive/projects/apps-python/egyPyramid-guardian-ultra/downloader_new/core/orchestrator.py
import os
import re
import time
import shutil
import asyncio
import random
import subprocess
import string
from downloader_new.db.supabase_client import supabase, initialize_supabase_record
from downloader_new.metadata.formatter import get_clean_media_data
from downloader_new.metadata.formatter import extract_clean_media_info
from downloader_new.metadata.formatter import normalize_title
from downloader_new.metadata.tmdb_client import fetch_tmdb_metadata
from downloader_new.metadata.formatter import build_display_title
from downloader_new.shared.logger import get_beast_logger
from downloader_new.shared.helpers import get_smart_headers
from downloader_new.core.workspace import setup_workspace, ensure_dependencies
from downloader_new.core.task_runner import run_pyramid_tasks, finalize_episode
from downloader_new.uploaders.archive import process_archive_upload
from downloader_new.uploaders.uploader_hub import upload_to_all_servers
from downloader_new.extractors.playwright_ext import resolve_direct_url
from downloader_new.media.downloader import build_ytdlp_command, download_video
from downloader_new.media.processor import extract_archive, apply_media_disguise
from downloader_new.media.file_manager import (
    check_media_duplicate,
    rename_and_move_to_stream,
    list_videos,
)

log = get_beast_logger("GuardianUltra")


def get_space_stream_url(file_name):
    # نحاول جلب القيمة من النظام، إذا فشل أو لم تكن موجودة، نستخدم قيمة افتراضية
    space_id = os.environ.get("SPACE_ID")

    # إذا كان النظام لم يقم بتعريفه أو كان فارغاً، نضع القيمة الافتراضية الخاصة بنا
    if not space_id:
        space_id = "egystreamer/guardian-ultra"

    space_domain = space_id.replace("/", "-").strip()
    return f"https://{space_domain}.hf.space/stream/{file_name}"


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

    # --- 3. تحديد query البحث وتنظيف البيانات ---
    if "http" in original_task_name or original_task_name.startswith(("tt", "tmdb")):
        search_query_clean = original_task_name
    else:
        clean_res = get_clean_media_data(original_task_name)
        log.info(f"DEBUG: calling get_clean_media_data with {original_task_name}")
        if clean_res and len(clean_res) == 4:
            search_query_clean, pre_category, pre_season, pre_ep = clean_res
            search_query_clean_tmdb = normalize_title(
                search_query_clean, for_search=True
            )
        else:
            search_query_clean_tmdb = normalize_title(
                original_task_name, for_search=True
            )
            search_query_clean = search_query_clean_tmdb
            pre_category, pre_season, pre_ep = "movie", None, None

    # --- 4. فحص التكرار السريع (مقدم لتوفير الموارد) ---
    # نفحص قاعدة البيانات بالاسم والسنة المستخرجين محلياً قبل استدعاء أي API خارجي
    try:
        fast_dup_check = check_media_duplicate(
            search_query_clean,
            extracted_year,
            pre_category,
            pre_season,
            pre_ep,
        )
        if fast_dup_check["exists"] and pre_category == "movie":
            log.info(
                f"✅ [تخطي مبكر]: الفيلم '{original_task_name}' موجود بالفعل! (وفرنا استدعاء TMDB)"
            )
            return
    except Exception as e:
        log.warning(f"⚠️ فشل الفحص السريع للتكرار، سنكمل المسار الطبيعي: {e}")

    # --- 5. جلب بيانات TMDB ---
    tmdb_data = fetch_tmdb_metadata(
        search_query_clean_tmdb if search_query_clean_tmdb else name,
        year=extracted_year,
    )
    log.info(
        f"DEBUG: Final media data - Title: {tmdb_data['display_title']}, Year: {tmdb_data['year']}"
    )
    if not tmdb_data.get("year") or tmdb_data["year"] == "غير محدد":
        year_match = re.search(r"(19|20)\d{2}", original_task_name)
        if year_match:
            tmdb_data["year"] = year_match.group(0)
            log.info(f"📅 Fallback Year = {tmdb_data['year']}")
    # --- 6. بناء الاسم المعروض النهائي وتحديث بيانات التنظيف ---
    display_title = build_display_title(original_task_name, tmdb_data["display_title"])
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

    # --- 7. فحص التكرار الدقيق (احتياطي بعد جلب البيانات الرسمية) ---
    try:
        dup_check = check_media_duplicate(
            clean_title_search,
            tmdb_data["year"],
            category_search,
            current_season_no,
            current_ep_no,
        )
        if dup_check["exists"] and category_search == "movie":
            log.info(
                f"✅ [تخطي دقيق]: الفيلم '{display_title}' مسجل مسبقاً بناءً على بيانات TMDB!"
            )
            return
    except Exception as e:
        log.warning(f"⚠️ فشل الفحص الدقيق للتكرار: {e}")

    # --- 8. الحجز الأولي في Supabase ---
    temp_id = f"loading_{timestamp}"
    e_id, media_id, meta_story, final_poster = initialize_supabase_record(
        display_title, original_task_name, tmdb_data, temp_id
    )

    if e_id is None and media_id is None:
        return

    if not e_id:
        log.warning("⚠️ فشل الحصول على ID من ساب باز، لن نتمكن من عرض التقدم الحي.")

    # سحب بيانات tmdb للمتغيرات المحلية بأمان
    tmdb_id_fetched = tmdb_data.get("tmdb_id")
    meta_labels = tmdb_data.get("labels")
    meta_duration = tmdb_data.get("duration")
    meta_rating = tmdb_data.get("rating")
    meta_runtime = tmdb_data.get("runtime")
    meta_year = tmdb_data.get("year")

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
        final_public_path, direct_remote_url = rename_and_move_to_stream(
            actual_downloaded_path, media_id, e_id, 1
        )
        actual_downloaded_path = final_public_path
        vid_path = final_public_path
        final_direct_url = direct_remote_url  # حفظ الرابط الديناميكي
        log.info(f"final_direct_url for local file: {final_direct_url}")

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
        actual_downloaded_path = await download_video(
            cmd, task_id, display_title, extract_dir
        )

        if actual_downloaded_path:
            final_public_path, direct_remote_url = rename_and_move_to_stream(
                actual_downloaded_path, media_id, e_id, 1
            )
            actual_downloaded_path = final_public_path
            vid_path = final_public_path
            final_direct_url = direct_remote_url  # حفظ الرابط الديناميكي

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
            # بعد فك الضغط، جرد الفيديوهات من المجلد المستخرج
            videos = list_videos(extract_dir)
        else:
            log.info(f"🎬 تم اكتشاف فيديو، جاري التحضير للرفع...")
            # الملف موجود بالفعل في المسار الصحيح (vid_path)
            videos = [vid_path]
            log.info(
                f"videos={vid_path} | is_rar={is_rar} | is_local_file={is_local_file}"
            )
        # لا تقم بإعادة تعريف videos مرة أخرى باستخدام list_videos(extract_dir) هنا!
        # انتقل مباشرة إلى فحص عدد الفيديوهات
        if not videos:
            if "vid_path" in locals() and os.path.exists(vid_path):
                videos = [vid_path]
                log.info(
                    f"videos={vid_path} | is_rar={is_rar} | is_local_file={is_local_file}"
                )
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
            apply_media_disguise(vid_path, idx, display_title, LOGO_FILE)
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
                    dup_check = check_media_duplicate(
                        c_title_l, meta_year, "tv", c_season_l, c_ep_l
                    )
                    if dup_check["exists"]:
                        log.info(
                            f"✅ [تخطي]: الحلقة {c_ep_l} من الموسم {c_season_l} موجودة ولها روابط!"
                        )
                        continue
                    elif dup_check["media_id"]:
                        log.info(f"🔄 [تحديث]: الحلقة {c_ep_l} موجودة بدون روابط...")
                else:
                    log.warning(
                        f"⚠️ فشل تنظيف بيانات الحلقة {loop_display_title} - سيتم تجاوز فحص التكرار"
                    )

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
                log.info(
                    f"🔗 [Direct Link] استخدام الرابط الديناميكي: {final_direct_url}"
                )
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
                file_name = os.path.basename(vid_path)

                # استبدال السطرين اليدويين بهذا الاستدعاء:
                remote_source = get_space_stream_url(file_name)

                log.info(
                    f"✅ المصدر المعتمد للرفع الخماسي: [Direct Stream] - {remote_source}"
                )
                await asyncio.sleep(10)

                upload_results = await upload_to_all_servers(
                    vid_path,
                    episode_label,
                    media_id,
                    e_id,
                    remote_source,
                    task_id,
                    final_file_name,
                )
            else:
                upload_results = {
                    "vk_url": "Failed",
                    "voe_watch": "Failed",
                    "voe_download": "Failed",
                    "dood_url": None,
                    "tape_url": None,
                    "lulu_url": None,
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
