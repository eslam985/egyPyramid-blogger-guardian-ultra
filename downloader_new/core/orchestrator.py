import os
import re
import time
import shutil
import asyncio
import random
import subprocess
import string

from downloader_new.db.supabase_client import supabase, initialize_supabase_record
from downloader_new.metadata.formatter import (
    get_clean_media_data,
    extract_clean_media_info,
    normalize_title,
    build_display_title,
)
from downloader_new.metadata.tmdb_client import fetch_tmdb_metadata
from downloader_new.shared.logger import get_beast_logger
from downloader_new.shared.helpers import get_smart_headers
from downloader_new.core.workspace import setup_workspace, ensure_dependencies
from downloader_new.core.task_runner import run_pyramid_tasks, finalize_episode
from downloader_new.uploaders.archive import process_archive_upload
from downloader_new.uploaders.uploader_hub import upload_to_all_servers
from downloader_new.extractors.playwright_ext import resolve_direct_url
from downloader_new.media.downloader import (
    build_ytdlp_command,
    download_video,
    is_direct_cdn_link,
    build_curl_command,
    download_video_curl,
)
from downloader_new.media.processor import extract_archive, apply_media_disguise
from downloader_new.media.file_manager import (
    check_media_duplicate,
    rename_and_move_to_stream,
    list_videos,
)

log = get_beast_logger("orchestrator.py")


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def get_space_stream_url(file_name: str) -> str:
    space_id = os.environ.get("SPACE_ID") or "egystreamer/guardian-ultra"
    space_domain = space_id.replace("/", "-").strip()
    return f"https://{space_domain}.hf.space/stream/{file_name}"


# ──────────────────────────────────────────────
# Step 1 — Workspace & Dependencies
# ──────────────────────────────────────────────

class WorkspaceInitializer:
    """يجهّز بيئة العمل ويتحقق من الأدوات المطلوبة."""

    async def initialize(self) -> dict:
        ws = setup_workspace()
        try:
            await ensure_dependencies()
        except Exception as e:
            log.warning(f"⚠️ فشل فحص الأدوات (تجاوز): {e}")
        return ws


# ──────────────────────────────────────────────
# Step 2 — Metadata Resolution
# ──────────────────────────────────────────────

class MetadataResolver:
    """
    يستخرج البيانات الوصفية من الاسم الخام ثم من TMDB،
    ويوحّد السنة بين المصدرين.
    """

    def resolve(self, name: str, meta_data: dict | None) -> dict:
        original_task_name, extracted_year = extract_clean_media_info(name)
        search_query_clean, pre_category, pre_season, pre_ep = \
            self._parse_clean_data(original_task_name)

        trailer_url = meta_data.get("trailer_url") if isinstance(meta_data, dict) else None
        search_for_tmdb = normalize_title(search_query_clean, for_search=True)

        tmdb_data = fetch_tmdb_metadata(
            search_for_tmdb or name,
            year=extracted_year,
            trailer_url=trailer_url,
        )

        tmdb_data["year"] = self._resolve_year(tmdb_data, extracted_year, original_task_name)

        log.info(f"DEBUG: Final media data — Title: {tmdb_data['display_title']}, Year: {tmdb_data['year']}")

        return {
            "original_task_name": original_task_name,
            "extracted_year":     extracted_year,
            "search_query_clean": search_query_clean,
            "pre_category":       pre_category,
            "pre_season":         pre_season,
            "pre_ep":             pre_ep,
            "tmdb_data":          tmdb_data,
        }

    # ── private ──

    def _parse_clean_data(self, name: str) -> tuple:
        if "http" in name or name.startswith(("tt", "tmdb")):
            return name, "movie", None, None

        log.info(f"DEBUG: calling get_clean_media_data with {name}")
        result = get_clean_media_data(name)
        if result and len(result) == 4:
            return result  # (clean_title, category, season, ep)

        fallback = normalize_title(name, for_search=True)
        return fallback, "movie", None, None

    def _resolve_year(self, tmdb_data: dict, extracted_year, original_name: str) -> str:
        if extracted_year:
            if tmdb_data.get("year") != str(extracted_year):
                log.info(
                    f"🔄 تصحيح السنة من {tmdb_data.get('year')} (TMDB) "
                    f"إلى {extracted_year} (العنوان الأصلي)"
                )
            return str(extracted_year)

        # Fallback: استخراج من الاسم الأصلي
        if not tmdb_data.get("year") or tmdb_data["year"] == "غير محدد":
            match = re.search(r"(19|20)\d{2}", original_name)
            if match:
                log.info(f"📅 Fallback Year = {match.group(0)}")
                return match.group(0)

        return tmdb_data.get("year", "غير محدد")


# ──────────────────────────────────────────────
# Step 3 — Duplicate Check
# ──────────────────────────────────────────────

class DuplicateGuard:
    """يفحص التكرار مرتين: مبكراً بالبيانات المحلية، ودقيقاً بعد TMDB."""

    def fast_check(self, search_query, year, category, season, ep) -> bool:
        """يُرجع True لو المحتوى موجود ويجب التخطي."""
        try:
            result = check_media_duplicate(search_query, year, category, season, ep)
            if result["exists"] and category == "movie":
                log.info(f"✅ [تخطي مبكر]: '{search_query}' موجود بالفعل! (وفرنا استدعاء TMDB)")
                return True
        except Exception as e:
            log.warning(f"⚠️ فشل الفحص السريع للتكرار، سنكمل: {e}")
        return False

    def precise_check(self, display_title, year, category, season, ep) -> bool:
        """يُرجع True لو المحتوى موجود ويجب التخطي."""
        try:
            result = check_media_duplicate(display_title, year, category, season, ep)
            if result["exists"] and category == "movie":
                log.info(f"✅ [تخطي دقيق]: '{display_title}' مسجل مسبقاً بناءً على بيانات TMDB!")
                return True
        except Exception as e:
            log.warning(f"⚠️ فشل الفحص الدقيق للتكرار: {e}")
        return False

    def episode_check(self, loop_display_title: str, meta_year: str) -> tuple[bool, dict | None]:
        """
        يفحص تكرار حلقة مسلسل.
        يُرجع (should_skip, dup_result).
        """
        clean = get_clean_media_data(loop_display_title)
        if not (clean and len(clean) == 4):
            log.warning(f"⚠️ فشل تنظيف بيانات الحلقة {loop_display_title} - تجاوز فحص التكرار")
            return False, None

        c_title, _, c_season, c_ep = clean
        try:
            dup = check_media_duplicate(c_title, meta_year, "tv", c_season, c_ep)
            if dup["exists"]:
                log.info(f"✅ [تخطي]: الحلقة {c_ep} من الموسم {c_season} موجودة ولها روابط!")
                return True, dup
            elif dup["media_id"]:
                log.info(f"🔄 [تحديث]: الحلقة {c_ep} موجودة بدون روابط...")
            return False, dup
        except Exception as e:
            log.warning(f"⚠️ فشل فحص تكرار الحلقة: {e}")
            return False, None


# ──────────────────────────────────────────────
# Step 4 — Supabase Record Initializer
# ──────────────────────────────────────────────

# في RecordInitializer.initialize — بعد الحجز الأولي
# احفظ الـ identifier الحقيقي فور ما يتحدد

class RecordInitializer:
    def initialize(self, display_title, original_task_name, tmdb_data, timestamp) -> tuple:
        temp_id = f"loading_{timestamp}"
        e_id, media_id, meta_story, final_poster = initialize_supabase_record(
            display_title, original_task_name, tmdb_data, temp_id
        )
        if not e_id:
            log.warning("⚠️ فشل الحصول على episode ID")
        return e_id, media_id, meta_story, final_poster  # ← 4 قيم فقط


# ──────────────────────────────────────────────
# Step 5 — Download Manager
# ──────────────────────────────────────────────

class DownloadManager:
    """
    يقرر طريقة التحميل المناسبة ويُرجع:
    (actual_downloaded_path, final_direct_url)
    يرمي RuntimeError لو فشل التحميل.
    """

    async def acquire(self, url: str, extract_dir: str, timestamp: int,
                      task_id, display_title: str) -> tuple[str, str | None]:
        if os.path.exists(url):
            return self._handle_local_file(url)

        return await self._handle_remote_url(url, extract_dir, timestamp, task_id, display_title)

    # ── private ──

    def _handle_local_file(self, url: str) -> tuple[str, str | None]:
        log.info(f"♻️ اكتشاف ملف محلي: {url} — سيتم تخطي التحميل.")
        # الـ rename/move يحدث في المرحلة التالية (PostDownloadProcessor)
        return url, None

    async def _handle_remote_url(self, url: str, extract_dir: str, timestamp: int,
                              task_id, display_title: str) -> tuple[str, str | None]:
        log.info("📡 رابط ويب، جاري التجهيز للسحب...")

        download_template = os.path.join(extract_dir, f"temp_dl_{timestamp}.%(ext)s")

        # جيب الـ fallbacks من DB لو في task_id
        fallback_urls = []
        if task_id:
            try:
                res = supabase.table("download_tasks").select("fallback_urls").eq("id", task_id).execute()
                fallback_urls = (res.data[0].get("fallback_urls") or []) if res.data else []
                if fallback_urls:
                    log.info(f"🔗 وجدنا {len(fallback_urls)} fallback(s) للمهمة")
            except Exception as e:
                log.warning(f"⚠️ فشل جلب الـ fallbacks: {e}")

        # حاول الـ primary الأول
        all_urls = [url] + fallback_urls

        last_error = None
        for attempt_url in all_urls:
            try:
                log.info(f"🎯 جاري المحاولة: {attempt_url[:60]}...")
                # استخراج الرابط المباشر لكل السيرفرات (بما فيها vidtube)
                resolved_url = await resolve_direct_url(attempt_url)
                
                # استخدام curl المخصص للرابط المباشر لـ vidtube (أو cdn-video)، أو yt-dlp للبقية
                if is_direct_cdn_link(resolved_url) or "vidtube" in attempt_url or "cdn-tube" in attempt_url:
                    output_path = os.path.join(extract_dir, f"temp_dl_{timestamp}.mp4")
                    curl_cmd = build_curl_command(resolved_url, output_path)
                    path = await download_video_curl(curl_cmd, display_title, extract_dir, direct_url=resolved_url)
                else:
                    smart_headers = get_smart_headers(resolved_url)
                    cmd = build_ytdlp_command(resolved_url, download_template, smart_headers)
                    path = await download_video(cmd, task_id, display_title, extract_dir)
                
                log.info(f"✅ نجح التحميل من: {attempt_url[:60]}")
                return path, None

            except Exception as e:
                last_error = e
                log.warning(f"⚠️ فشل: {attempt_url[:60]} — {e}")
                if attempt_url != all_urls[-1]:
                    log.info("🔄 جاري تجربة الرابط التالي...")

        raise RuntimeError(f"فشلت كل الروابط ({len(all_urls)}). آخر خطأ: {last_error}")



# ──────────────────────────────────────────────
# Step 6 — Post-Download Processor
# ──────────────────────────────────────────────

class PostDownloadProcessor:
    """
    بعد التحميل:
    - ينقل الملف للمسار النهائي
    - يكتشف لو RAR → يفك الضغط
    - يُرجع قائمة الفيديوهات الجاهزة
    """

    def process(self, downloaded_path: str, media_id, e_id,
                extract_dir: str, is_local: bool) -> tuple[list[str], str, str | None]:
        """
        يُرجع (videos, vid_path, final_direct_url).
        vid_path = المسار بعد النقل.
        """
        final_path, direct_url = rename_and_move_to_stream(downloaded_path, media_id, e_id, 1)
        log.info(f"final_direct_url: {direct_url}")

        file_info = subprocess.getoutput(f'file "{final_path}"').lower()
        is_rar = "rar archive" in file_info or "zip archive" in file_info

        if is_rar and not is_local:
            log.info("🔓 تم اكتشاف ملف مضغوط حقيقي، جاري فك الضغط...")
            extract_archive(final_path, extract_dir)
            videos = list_videos(extract_dir)
        else:
            label = "ملف محلي جاهز" if is_local else "فيديو مباشر"
            log.info(f"🎬 {label}: جاري التحضير للرفع...")
            videos = [final_path]

        if not videos:
            if os.path.exists(final_path):
                videos = [final_path]
            else:
                raise RuntimeError("❌ لم يتم العثور على فيديوهات بعد المعالجة!")

        return videos, final_path, direct_url


# ──────────────────────────────────────────────
# Step 7 — Multi-Episode Splitter
# ──────────────────────────────────────────────

class MultiEpisodeSplitter:
    """
    لو في أكثر من فيديو واحد، يفرّخ مهام جديدة ويُرجع True.
    لو فيديو واحد فقط، يُرجع False.
    """

    async def split_if_needed(self, videos: list, display_title: str,
                               task_id, extract_dir: str) -> bool:
        if len(videos) <= 1:
            return False

        log.info(f"🎊 كنز! تم اكتشاف {len(videos)} حلقة. جاري إعادة توزيع المهام...")

        new_task_list = [
            {"url": vid, "name": f"{display_title} {os.path.basename(vid)}"}
            for vid in videos
        ]

        if task_id:
            supabase.table("download_tasks").update({
                "status_message": f"✅ تم تفكيك الملف لـ {len(videos)} حلقة، جاري المعالجة الفردية...",
                "status": "completed",
            }).eq("id", task_id).execute()

        await run_pyramid_tasks(new_task_list)

        if os.path.exists(extract_dir):
            shutil.rmtree(extract_dir)

        return True


# ──────────────────────────────────────────────
# Step 8 — Episode Processor (per-video loop)
# ──────────────────────────────────────────────

class EpisodeProcessor:
    """
    يعالج كل فيديو على حدة داخل اللووب:
    disguise → أرشفة → رفع → إنهاء
    """

    def __init__(self, duplicate_guard: DuplicateGuard):
        self._dup = duplicate_guard

    async def process_all(
        self,
        videos: list[str],
        display_title: str,
        final_direct_url: str | None,
        category_search: str,
        meta_year: str,
        media_id,
        e_id,
        task_id,
        tmdb_data: dict,
        original_task_name: str,
        meta_story: str,
        final_poster: str,
        url: str,
        logo_file: str,
    ):
        for idx, vid_path in enumerate(videos, 1):
            await self._process_one(
                idx=idx,
                vid_path=vid_path,
                videos=videos,
                display_title=display_title,
                final_direct_url=final_direct_url,
                category_search=category_search,
                meta_year=meta_year,
                media_id=media_id,
                e_id=e_id,
                task_id=task_id,
                tmdb_data=tmdb_data,
                original_task_name=original_task_name,
                meta_story=meta_story,
                final_poster=final_poster,
                url=url,
                logo_file=logo_file,
            )

    async def _process_one(self, idx: int, vid_path: str, videos: list,
                            display_title: str, final_direct_url: str | None,
                            category_search: str, meta_year: str,
                            media_id, e_id, task_id,
                            tmdb_data: dict, original_task_name: str,
                            meta_story: str, final_poster: str,
                            url: str, logo_file: str):

        loop_display_title = (
            f"{display_title} {os.path.basename(vid_path)}"
            if len(videos) > 1 else display_title
        )
        
        # فحص تكرار الحلقة لو مسلسل
        if category_search == "tv":
            should_skip, _ = self._dup.episode_check(loop_display_title, meta_year)
            if should_skip:
                return

        # تطبيق الـ disguise
        apply_media_disguise(vid_path, idx, display_title, logo_file)

        # بناء المعرّفات
        rand_id      = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
        final_file   = f"f_{media_id}_{e_id}_{idx}.mp4"

        log.info(f"📦 أرشفة النسخة الكاملة: {loop_display_title}")
        archive_url = process_archive_upload(vid_path, media_id, e_id, idx, task_id)

        # تحديث الحالة قبل الرفع
        if e_id:
            try:
                supabase.table("episodes").update({
                    "status_message": "🚀 جاري الضخ للسيرفرات الخماسية عبر الرابط المباشر...",
                    "progress_percent": 85,
                }).eq("id", e_id).execute()
            except Exception:
                pass

        # الرفع المتوازي
        upload_results = await self._upload(
            vid_path, loop_display_title, media_id, e_id, task_id, final_file, final_direct_url
        )

        # الإنهاء النهائي
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
            meta_rating=tmdb_data.get("rating"),
            meta_labels=tmdb_data.get("labels"),
            meta_runtime=tmdb_data.get("runtime"),
            meta_duration=tmdb_data.get("duration"),
            video_path=vid_path,
            archive_url=archive_url,
            url=url,
            c_title=tmdb_data.get("display_title"),  # ← أضف هذا السطر!

        )

    async def _upload(self, vid_path: str, label: str, media_id, e_id,
                       task_id, final_file: str, final_direct_url: str | None) -> dict:
        if not (vid_path and os.path.exists(vid_path)):
            log.warning("⚠️ الملف غير موجود — سيتم تخطي الرفع")
            return {"vk_url": "Failed", "voe_watch": "Failed",
                    "voe_download": "Failed", "dood_url": None,
                    "tape_url": None, "lulu_url": None}

        file_name     = os.path.basename(vid_path)
        remote_source = get_space_stream_url(file_name)

        if final_direct_url:
            log.info(f"🔗 [Direct Link] استخدام الرابط الديناميكي: {final_direct_url}")
        else:
            log.warning("⚠️ الرابط الديناميكي غير متاح، سيتم استخدام الرابط الأصلي")

        log.info(f"✅ المصدر المعتمد للرفع الخماسي: [Direct Stream] - {remote_source}")
        await asyncio.sleep(10)

        return await upload_to_all_servers(
            vid_path, label, media_id, e_id, remote_source, task_id, final_file
        )


# ──────────────────────────────────────────────
# Failure Handler
# ──────────────────────────────────────────────

class DownloadFailureHandler:
    """ينظّف الميديا ويعلّم التاسك بالفشل لما يفشل التحميل."""

    def handle(self, media_id, task_id, reason: str):
        if not media_id:
            return
        try:
            supabase.table("medias").delete().eq("id", media_id).execute()
            log.info(f"🧹 تم حذف سجل الميديا الفارغ (ID: {media_id})")
            if task_id:
                supabase.table("download_tasks").update({
                    "status": "failed",
                    "status_message": f"❌ فشل: {reason}",
                }).eq("id", task_id).execute()
        except Exception as e:
            log.warning(f"⚠️ فشل تنظيف الميديا: {e}")


# ──────────────────────────────────────────────
# Main Orchestrator
# ──────────────────────────────────────────────

async def pyramid_ultimate_beast(url: str, name: str, task_id=None, meta_data=None):
    """
    نقطة الدخول الرئيسية — تنسّق كل الخطوات بالترتيب:
    1.  تجهيز البيئة
    2.  استخراج الاسم والسنة محلياً (بدون TMDB)
    3.  فحص تكرار مبكر (محلي)
    4.  التحميل أولاً — لو فشل نوقف فوراً بدون أي سجلات
    5.  جلب TMDB (بعد التأكد إن الرابط شغال)
    6.  فحص تكرار دقيق (بعد TMDB)
    7.  الحجز الأولي في Supabase
    8.  المعالجة وفك الضغط
    9.  تفريخ المهام لو أكثر من حلقة
    10. معالجة كل حلقة (disguise → أرشفة → رفع → إنهاء)
    """
    timestamp = int(time.time())

    # 1. تجهيز البيئة
    ws = await WorkspaceInitializer().initialize()
    BASE_DIR  = ws["BASE_DIR"]
    LOGO_FILE = ws["LOGO_FILE"]

    # 2. استخراج الاسم والسنة محلياً فقط (بدون TMDB بعد)
    original_task_name, extracted_year = extract_clean_media_info(name)
    clean_local, pre_category, pre_season, pre_ep = \
        MetadataResolver()._parse_clean_data(original_task_name)

    dup_guard = DuplicateGuard()

    # 3. فحص تكرار مبكر بالبيانات المحلية
    if dup_guard.fast_check(clean_local, extracted_year, pre_category, pre_season, pre_ep):
        return

    # 4. جلب TMDB — للحصول على البيانات الدقيقة قبل التحميل
    meta      = MetadataResolver().resolve(name, meta_data)
    tmdb_data = meta["tmdb_data"]
    pre_category = meta["pre_category"]
    pre_season   = meta["pre_season"]
    pre_ep       = meta["pre_ep"]

    # 5. بناء الاسم المعروض + فحص تكرار دقيق (قبل التحميل)
    display_title = build_display_title(original_task_name, tmdb_data["display_title"])
    clean_res_db  = get_clean_media_data(display_title)
    if clean_res_db and len(clean_res_db) == 4:
        clean_title_search, category_search, current_season_no, current_ep_no = clean_res_db
        if category_search == "movie" and any(kw in original_task_name for kw in ["الموسم", "الحلقة", "مسلسل"]):
            category_search = "tv"
            current_season_no = pre_season
            current_ep_no = pre_ep
    else:
        clean_title_search  = display_title
        if any(kw in original_task_name for kw in ["الموسم", "الحلقة", "مسلسل", "Season", "Episode"]):
            category_search = "tv"
        else:
            category_search = "movie"
        current_season_no   = pre_season
        current_ep_no       = pre_ep

    if dup_guard.precise_check(clean_title_search, tmdb_data["year"],
                                category_search, current_season_no, current_ep_no):
        log.info(f"✅ تم العثور على الحلقة/الفيلم بالفعل، سيتم إيقاف المهمة وتخطي التحميل.")
        if task_id:
            supabase.table("download_tasks").update({
                "status": "completed",
                "status_message": "✅ متوفرة مسبقاً (تم تخطي التحميل)",
                "progress_percent": 100
            }).eq("id", task_id).execute()
        return

    # 6. التحميل الفعلي — يتم الآن فقط بعد التأكد من أن العمل غير موجود
    is_local    = os.path.exists(url)
    extract_dir = os.path.join(BASE_DIR, f"extracted_{timestamp}")
    os.makedirs(extract_dir, exist_ok=True)

    try:
        if task_id:
            supabase.table("download_tasks").update({
                "status_message": "📥 جاري التحميل...",
            }).eq("id", task_id).execute()
            
        downloaded_path, _ = await DownloadManager().acquire(
            url, extract_dir, timestamp, task_id, original_task_name
        )
    except Exception as e:
        log.error(f"❌ فشل التحميل (لم يُنشأ أي سجل): {e}")
        if task_id:
            supabase.table("download_tasks").update({
                "status": "failed",
                "status_message": f"❌ فشل التحميل: {str(e)[:100]}",
            }).eq("id", task_id).execute()
        shutil.rmtree(extract_dir, ignore_errors=True)
        return

    # 7. الحجز الأولي في Supabase — بعد التأكد من الرابط والتكرار
    e_id, media_id, meta_story, final_poster = RecordInitializer().initialize(
    display_title, original_task_name, tmdb_data, timestamp
)
    if e_id is None and media_id is None:
        shutil.rmtree(extract_dir, ignore_errors=True)
        return

    meta_year       = tmdb_data.get("year")
    failure_handler = DownloadFailureHandler()

    # 8. المعالجة وفك الضغط
    if task_id:
        supabase.table("download_tasks").update({
            "status_message": "⚙️ جاري فحص الملف ومعالجته...",
            "progress_percent": 91,
            "download_speed": "Processing",
        }).eq("id", task_id).execute()

    try:
        videos, _, final_direct_url = PostDownloadProcessor().process(
            downloaded_path, media_id, e_id, extract_dir, is_local
        )
    except Exception as e:
        log.error(f"❌ فشل المعالجة: {e}")
        failure_handler.handle(media_id, task_id, str(e))
        shutil.rmtree(extract_dir, ignore_errors=True)
        return

    log.info(f"✅ تم اكتشاف {len(videos)} ملف. جاري المعالجة والرفع باسم: {display_title}")

    # 9. تفريخ المهام لو أكثر من حلقة
    was_split = await MultiEpisodeSplitter().split_if_needed(
        videos, display_title, task_id, extract_dir
    )
    if was_split:
        return

    # 10. معالجة كل حلقة
    await EpisodeProcessor(dup_guard).process_all(
        videos=videos,
        display_title=display_title,
        final_direct_url=final_direct_url,
        category_search=category_search,
        meta_year=meta_year,
        media_id=media_id,
        e_id=e_id,
        task_id=task_id,
        tmdb_data=tmdb_data,
        original_task_name=original_task_name,
        meta_story=meta_story,
        final_poster=final_poster,
        url=url,
        logo_file=LOGO_FILE,
    )

    # تنظيف مجلد الاستخراج
    if os.path.exists(extract_dir):
        shutil.rmtree(extract_dir)

    log.info("\n✨ المهمة انتهت بنجاح!")