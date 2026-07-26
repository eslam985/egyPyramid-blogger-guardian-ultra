
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
    فحص احترافي لمنع التكرار.
    يعتمد على:
      - السنة أولاً.
      - ثم مقارنة normalize_title() بدلاً من ilike.
      - ثم فحص الحلقة والروابط للمسلسلات.
    """

    result = {
        "exists": False,
        "media_id": None,
        "episode_id": None,
    }

    try:
        # -----------------------------
        # 1) السنة إجبارية
        # -----------------------------
        if not year or str(year).strip() in ("", "None", "غير محدد"):
            log.warning(
                f"⚠️ تم تخطي فحص التكرار لأن السنة غير صالحة: {year}"
            )
            return result

        normalized_search = normalize_title(clean_title)

        # -----------------------------
        # 2) جلب كل أعمال نفس السنة فقط
        # -----------------------------
        medias = (
            supabase.table("medias")
            .select("id,title,year")
            .eq("year", str(year))
            .execute()
        )

        media_row = None

        if medias.data:
            for row in medias.data:

                db_title = row.get("title") or ""

                if normalize_title(db_title) == normalized_search:
                    media_row = row
                    break

        if not media_row:
            log.info(
                f"🔍 غير موجود: '{clean_title}' ({year})"
            )
            return result

        media_id = media_row["id"]

        result["media_id"] = media_id

        # ===========================================
        # الأفلام
        # ===========================================
        if category == "movie":

            episode = (
                supabase.table("episodes")
                .select("id")
                .eq("media_id", media_id)
                .limit(1)
                .execute()
            )

            if episode.data:
                result["exists"] = True
                result["episode_id"] = episode.data[0]["id"]

            log.info(
                f"🎬 Duplicate(Movie): exists={result['exists']} media={media_id}"
            )

            return result

        # ===========================================
        # المسلسلات
        # ===========================================
        if category == "tv":

            if season_no is None or ep_no is None:
                return result

            season = (
                supabase.table("seasons")
                .select("id")
                .eq("media_id", media_id)
                .eq("season_number", season_no)
                .limit(1)
                .execute()
            )

            if not season.data:
                return result

            season_id = season.data[0]["id"]

            episode = (
                supabase.table("episodes")
                .select("id")
                .eq("media_id", media_id)
                .eq("season_id", season_id)
                .eq("episode_number", ep_no)
                .limit(1)
                .execute()
            )

            if not episode.data:
                return result

            episode_id = episode.data[0]["id"]

            result["episode_id"] = episode_id

            links = (
                supabase.table("links")
                .select("id")
                .eq("episode_id", episode_id)
                .limit(1)
                .execute()
            )

            if links.data:
                result["exists"] = True

            log.info(
                f"📺 Duplicate(TV): exists={result['exists']} media={media_id} episode={episode_id}"
            )

        return result

    except Exception as e:
        log.warning(f"⚠️ فشل فحص التكرار: {e}")
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

