import os
from downloader_new.shared.logger import get_beast_logger
from downloader_new.db.supabase_client import supabase, save_to_supabase
from downloader_new.uploaders.telegram import send_to_telegram
from downloader_new.uploaders.others import upload_to_mixdrop

log = get_beast_logger("GuardianUltra")

mix_user = os.getenv("MIXDROP_EMAIL")
mix_key  = os.getenv("MIXDROP_API_KEY")


# ──────────────────────────────────────────────
# Anti Circular Import Bridge
# ──────────────────────────────────────────────

async def run_pyramid_tasks(task_list):
    """جسر لتجنب الـ Circular Import مع main_downloader."""
    from downloader_new.main_downloader import run_pyramid_tasks as _original
    return await _original(task_list)


# ──────────────────────────────────────────────
# Repository: عمليات DB المعزولة
# ──────────────────────────────────────────────

class EpisodeRepository:
    """كل عمليات جدول episodes في مكان واحد."""

    def update_status(self, episode_id, message: str, progress: int):
        supabase.table("episodes").update({
            "status_message": message,
            "progress_percent": progress,
        }).eq("id", episode_id).execute()

    def mark_complete(self, episode_id):
        try:
            supabase.table("episodes").update({
                "progress_percent": 100,
                "status_message": "✅ اكتملت المعالجة والرفع بنجاح",
                "download_speed": "Done",
            }).eq("id", episode_id).execute()
        except Exception as e:
            log.warning(f"⚠️ فشل تحديث حالة الحلقة: {e}")

    def count_links(self, episode_id) -> int:
        res = (
            supabase.table("links")
            .select("id", count="exact")
            .eq("episode_id", episode_id)
            .execute()
        )
        return res.count or 0


class MediaRepository:
    """كل عمليات جدول medias في مكان واحد."""

    def mark_ready(self, media_id):
        supabase.table("medias").update({"is_ready": True}).eq("id", media_id).execute()

    def delete(self, media_id):
        supabase.table("medias").delete().eq("id", media_id).execute()
        log.warning(f"🗑️ تم حذف الميديا {media_id} لعدم وجود روابط كافية.")


class TaskRepository:
    """كل عمليات جدول download_tasks في مكان واحد."""

    def close(self, task_id, status: str, message: str):
        try:
            supabase.table("download_tasks").update({
                "status": status,
                "progress_percent": 100,
                "status_message": message,
            }).eq("id", task_id).execute()
            log.info(f"✅ تم إغلاق التاسك {task_id} بحالة: {status}")
        except Exception as e:
            log.error(f"❌ فشل تحديث حالة التاسك: {e}")


class LinksRepository:
    """كل عمليات جدول links في مكان واحد."""

    def upsert(self, episode_id, server_name: str, url: str):
        supabase.table("links").upsert(
            {"episode_id": episode_id, "server_name": server_name, "url": url},
            on_conflict="episode_id, server_name",
        ).execute()


# ──────────────────────────────────────────────
# Services: منطق الأعمال المعزول
# ──────────────────────────────────────────────

class MixdropUploader:
    """مسؤول حصراً عن رفع الفيديو لـ MixDrop وحفظ الرابط."""

    def __init__(self, links_repo: LinksRepository, episode_repo: EpisodeRepository):
        self._links   = links_repo
        self._episode = episode_repo

    async def upload(self, episode_id, video_path: str):
        try:
            self._episode.update_status(episode_id, "💧 جاري الرفع لـ MixDrop...", 99)
            mix_url = await upload_to_mixdrop(video_path, mix_user, mix_key)
            if mix_url:
                self._links.upsert(episode_id, "mixdrop", mix_url)
                log.info(f"✅ تم رفع وحفظ رابط MixDrop: {mix_url}")
        except Exception as e:
            log.warning(f"⚠️ فشل MixDrop: {e}")


class QualityGate:
    """
    يحكم على جودة النتيجة النهائية:
    - هل فيه 3 سيرفرات على الأقل؟
    - هل البيانات الوصفية مكتملة؟
    """

    MIN_SERVERS = 3

    def __init__(self, episode_repo: EpisodeRepository, media_repo: MediaRepository):
        self._episode = episode_repo
        self._media   = media_repo

    def evaluate(self, episode_id, media_id, meta_story: str, final_poster: str) -> tuple[bool, bool]:
        """
        يُرجع (quality_pass, has_metadata).
        quality_pass  = True لو الروابط >= MIN_SERVERS
        has_metadata  = True لو الصورة والوصف موجودين
        """
        links_count  = self._episode.count_links(episode_id)
        has_metadata = bool(meta_story and meta_story.strip()) and bool(final_poster and final_poster.strip())
        quality_pass = links_count >= self.MIN_SERVERS

        if quality_pass and has_metadata:
            self._media.mark_ready(media_id)
            log.info(f"🚀 تم إطلاق إشارة الجاهزية الكاملة (سيرفرات: {links_count})")
        elif quality_pass:
            log.warning("🟡 تم الحفظ بنجاح ولكن بدون جاهزية (نقص في الصورة أو الوصف)")

        return quality_pass, has_metadata


class TelegramNotifier:
    """مسؤول حصراً عن إرسال إشعار تليجرام."""

    def notify(self, display_title: str, meta_story: str, final_poster: str,
               meta_labels: list, meta_year: str, category: str):
        row = {
            "title":      display_title,
            "story":      meta_story or "لا يوجد وصف متاح حالياً.",
            "poster_url": final_poster,
            "labels":     meta_labels,
            "year":       meta_year,
        }
        status = send_to_telegram(
            row=row,
            content_type=category,
            action_text="المشاهدة",
            post_url=final_poster,
            lang_val="لغة أصلية (مترجم)",
        )
        if status:
            log.info("✅ تم إرسال تمبلت تليجرام بنجاح")


class LocalFileCleaner:
    """مسؤول حصراً عن حذف الملف المحلي بعد الرفع."""

    def clean(self, video_path: str):
        if not os.path.exists(video_path):
            return
        try:
            os.remove(video_path)
            log.info(f"🗑️ تم تنظيف الملف المحلي: {os.path.basename(video_path)}")
        except Exception as e:
            log.warning(f"⚠️ لم يتم مسح الملف المؤقت: {e}")


# ──────────────────────────────────────────────
# Orchestrator: ينسّق كل الخطوات بالترتيب
# ──────────────────────────────────────────────

class EpisodeFinalizer:
    """
    ينسّق خطوات الإنهاء بالترتيب الصحيح:
    MixDrop ← حفظ Supabase ← جودة ← تليجرام ← إغلاق تاسك ← تنظيف
    """

    def __init__(self):
        episode_repo = EpisodeRepository()
        media_repo   = MediaRepository()
        links_repo   = LinksRepository()
        task_repo    = TaskRepository()

        self._mixdrop  = MixdropUploader(links_repo, episode_repo)
        self._quality  = QualityGate(episode_repo, media_repo)
        self._telegram = TelegramNotifier()
        self._cleaner  = LocalFileCleaner()
        self._tasks    = task_repo
        self._media    = media_repo
        self._episode  = episode_repo

    async def finalize(
        self,
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
        voe_watch = upload_results.get("voe_watch", "Failed")
        vk_url    = upload_results.get("vk_url",    "Failed")

        # 1. رفع MixDrop
        await self._mixdrop.upload(episode_id, video_path)

        # 2. الحفظ النهائي الشامل في Supabase
        save_res = self._save_to_supabase(
            voe_watch, vk_url, loop_display_title, original_task_name,
            meta_story, final_poster, meta_year, meta_rating,
            video_path, archive_url, tmdb_data, meta_labels, meta_runtime, meta_duration,
        )

        if not save_res:
            # فشل الحفظ الأساسي — نوقف هنا
            if task_id:
                self._tasks.close(task_id, "failed", "❌ فشل الحفظ النهائي في سوبابيز")
            return

        episode_id, media_id, meta_story, final_poster = save_res
        log.info("🏁 تم إغلاق المهمة بنجاح وحفظ كافة البيانات.")

        # 3. تقييم الجودة
        quality_pass, has_metadata = self._quality.evaluate(
            episode_id, media_id, meta_story, final_poster
        )

        # 4. إغلاق التاسك
        if task_id:
            self._close_task(task_id, media_id, quality_pass, has_metadata)

        # 5. إشعار تليجرام (فقط لو الجودة عدّت)
        if quality_pass:
            self._telegram.notify(
                loop_display_title, meta_story, final_poster,
                meta_labels, meta_year, category,
            )

        # 6. تنظيف الملف المحلي
        self._cleaner.clean(video_path)

        # 7. تحديث حالة الحلقة النهائية
        self._episode.mark_complete(episode_id)

    # ── Helpers ──

    def _save_to_supabase(self, voe_watch, vk_url, display_title, original_name,
                          meta_story, final_poster, meta_year, meta_rating,
                          video_path, archive_url, tmdb_data, meta_labels,
                          meta_runtime, meta_duration):
        try:
            return save_to_supabase(
                voe_watch, vk_url, display_title, original_name,
                meta_story, final_poster, meta_year, meta_rating,
                video_path, archive_url,
                tmdb_id=tmdb_data["tmdb_id"],
                labels=meta_labels,
                runtime=meta_runtime,
                duration_iso=meta_duration,
            )
        except Exception as e:
            log.error(f"❌ فشل التحديث النهائي في سوبابيز: {e}")
            return None

    def _close_task(self, task_id, media_id, quality_pass: bool, has_metadata: bool):
        if media_id and not quality_pass:
            self._media.delete(media_id)
            self._tasks.close(task_id, "failed", "❌ فشل: السيرفرات أقل من 3")
        else:
            msg = "✅ اكتملت بنجاح!" if has_metadata else "⚠️ اكتملت (بدون بيانات وصفية)"
            self._tasks.close(task_id, "completed", msg)


# ──────────────────────────────────────────────
# Public API (للاستخدام من الخارج)
# ──────────────────────────────────────────────

async def finalize_episode(**kwargs):
    """نقطة الدخول العامة — تفويض لـ EpisodeFinalizer."""
    await EpisodeFinalizer().finalize(**kwargs)