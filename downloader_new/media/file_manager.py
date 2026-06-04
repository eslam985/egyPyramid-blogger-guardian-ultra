
# /media/es/DDrive/projects/apps-python/egyPyramid-guardian-ultra/downloader_new/media/file_manager.py
import os 
import shutil
from downloader_new.metadata.formatter import normalize_title
from downloader_new.db.supabase_client import supabase
from downloader_new.shared.logger import get_beast_logger
log = get_beast_logger("GuardianUltra")


# ابحث عن دالة check_media_duplicate القديمة واستبدلها بالكامل بهذا المنطق الصارم:

def check_media_duplicate(clean_title: str, year: str, category: str, season_no, ep_no) -> dict:
    """
    التحقق الصارم والذكي من وجود الميديا/الحلقة مسبقاً في Supabase مع معالجة اختلافات الترقيم.
    """
    result = {"exists": False, "media_id": None, "episode_id": None}
    import re

    try:
        media_id = None
        
        # 1. بناء نمط البحث المرن (تغيير المسافات وعلامات الترقيم إلى %)
        smart_pattern = re.sub(r'[^a-zA-Z0-9\u0600-\u06FF]+', '%', clean_title)
        smart_pattern = f"%{smart_pattern}%"

        # 2. البحث الموحد والذكي في جدول الميديا باستخدام النمط والسنة معاً
        m_query = (
            supabase.table("medias")
            .select("id")
            .ilike("title", smart_pattern)
            .eq("year", year)
            .execute()
        )

        if m_query.data:
            media_id = m_query.data[0]["id"]

        result["media_id"] = media_id

        # 3. تتبع الحلقات والروابط بناءً على الفئة
        if media_id:
            if category == "movie":
                # فحص ما إذا كان للفيلم حلقة مسجلة بالفعل
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
                # فحص المسلسلات: الانتقال من السلسلة -> الموسم -> الحلقة -> الروابط
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
        log.warning(f"⚠️ فشل فحص التكرار الصارم: {e}")

    log.info(f"فحص التكرار: النمط='{smart_pattern}', السنة='{year}', الفئة='{category}', النتيجة: exists={result['exists']}, media_id={result['media_id']}")
    return result




def rename_and_move_to_stream(file_path, media_id, episode_id, idx):
    """
    إعادة تسمية الملف بالمعرفات الرقمية ونقله لمجلد stream.
    تعيد (final_public_path, direct_remote_url).
    """
    new_file_name = f"f_{media_id}_{episode_id}_{idx}.mp4"
    new_path = os.path.join(os.path.dirname(file_path), new_file_name)

    try:
        os.rename(file_path, new_path)
        file_path = new_path
        log.info(f"🔄 تم إعادة تسمية الملف إلى المعرف الرقمي: {new_file_name}")
    except Exception as rename_err:
        log.error(f"⚠️ فشل إعادة التسمية، سيتم استخدام الاسم الأصلي: {rename_err}")
        new_file_name = os.path.basename(file_path)


    base_root = os.path.dirname(os.getcwd())          # /app
    stream_dir = os.path.join(base_root, "stream")    # /app/stream

    final_public_path = os.path.join(stream_dir, new_file_name)
    try:
        shutil.copy2(file_path, final_public_path)
        if os.path.exists(file_path):
            os.remove(file_path)
        log.info(f"✅ تم تأمين الملف في المسار العام: {final_public_path}")
    except Exception as move_err:
        log.error(f"❌ خطأ في نقل الملف: {move_err}")

    raw_space_id = os.environ.get("SPACE_ID", "egystreamer/guardian-ultra")
    space_domain = raw_space_id.replace("/", "-").strip()
    direct_remote_url = f"https://{space_domain}.hf.space/stream/{new_file_name}"
    log.info(f"🔗 [Direct Link] الرابط جاهز للاختبار: {direct_remote_url}")

    return final_public_path, direct_remote_url


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

