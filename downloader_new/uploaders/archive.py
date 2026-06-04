# /media/es/DDrive/projects/apps-python/egyPyramid-guardian-ultra/downloader_new/uploaders/archive.py
import random
import string
import os
from tqdm import tqdm as tqdm_std
from downloader_new.db.supabase_client import supabase
from downloader_new.shared.logger import get_beast_logger
from downloader_new.uploaders.telegram import ProgressStream
log = get_beast_logger("GuardianUltra")


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
                "last_check_status": "pending",
            }
        ).execute()

        log.info(f"✅ تم الأرشفة بنجاح: {direct_download_url}")
        return direct_download_url  # مهم جداً للـ Loop

    except Exception as e:
        log.error(f"❌ خطأ أرشيف: {e}")
        return "Failed_Archive_Upload"




def process_archive_upload(video_path: str, media_id: int, episode_id: int, idx: int, task_id) -> str:
    """
    رفع نسخة احتياطية إلى Archive.org.
    تعيد رابط الأرشيف أو "Disabled" أو "Failed_Archive_Upload".
    """
    rand_id = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
    identifier = f"v{rand_id}x{media_id}x{episode_id}x{idx}"
    final_file_name = f"f_{media_id}_{episode_id}_{idx}.mp4"

    # archive_url = Upload_To_Archive(video_path, media_id, episode_id, idx, identifier, final_file_name, ARCHIVE_ACCESS_KEY, ARCHIVE_SECRET_KEY, task_id)
    archive_url = ""
    return archive_url


