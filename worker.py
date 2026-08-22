import httpx

# إجبار المكتبة عالمياً على إغلاق HTTP/2 وتفعيل HTTP/1.1 المستقر لمنع سقوط اتصال سوبابيس
def _patch_httpx_client(client_class):
    orig_init = client_class.__init__
    def patched_init(self, *args, **kwargs):
        kwargs["http2"] = False
        orig_init(self, *args, **kwargs)
    client_class.__init__ = patched_init

_patch_httpx_client(httpx.Client)
_patch_httpx_client(httpx.AsyncClient)

import os
import time
import random
import nest_asyncio
import asyncio
from downloader_new.shared.logger import get_beast_logger

PROJECT_ROOT = os.getcwd()
log = get_beast_logger("GuardianWorker")
log.info(f"🚀 تم تشغيل الووركر بنجاح من المسار: {PROJECT_ROOT}")

should_stop_worker = False

# ──────────────────────────────────────────────
# طبقة الوصول إلى البيانات (Repository Layer)
# ──────────────────────────────────────────────

class TaskRepository:
    """مسؤول حصراً عن العمليات المباشرة على جدول download_tasks."""

    def __init__(self, client):
        self._db = client

    def fetch_idle_tasks(self, limit: int = 5):
        res = (
            self._db.table("download_tasks")
            .select("*")
            .eq("status", "idle")
            .order("created_at", desc=False)
            .limit(limit)
            .execute()
        )
        return res.data or []

    def try_lock_task(self, job_id: str) -> bool:
        """يحاول قفل المهمة؛ يُرجع True إذا نجح، False إذا سبقه ووركر آخر."""
        res = (
            self._db.table("download_tasks")
            .update({
                "status": "processing",
                "status_message": "🚀 الوحش بدأ السحب والتحليل...",
                "progress_percent": 5,
            })
            .eq("id", job_id)
            .eq("status", "idle")
            .execute()
        )
        return bool(res.data)

    def mark_failed(self, job_id: str, reason: str):
        self._db.table("download_tasks").update({
            "status": "failed",
            "status_message": f"❌ فشل: {reason[:100]}",
        }).eq("id", job_id).execute()

    def get_status(self, job_id: str) -> str | None:
        res = (
            self._db.table("download_tasks")
            .select("status")
            .eq("id", job_id)
            .execute()
        )
        return res.data[0]["status"] if res.data else None
    
    def delete_if_completed(self, job_id: str):
        status = self.get_status(job_id)
        if status == "completed":
            self._db.table("download_tasks").delete().eq("id", job_id).execute()
            log.info(f"🗑️ تم حذف المهمة المكتملة {job_id}")

class MediaRepository:
    """مسؤول حصراً عن تنظيف سجلات medias/episodes عند الفشل."""

    def __init__(self, client):
        self._db = client

    def cleanup_by_title(self, title: str):
        res = (
            self._db.table("medias")
            .select("id")
            .ilike("title", f"%{title}%")
            .limit(1)
            .execute()
        )
        if not res.data:
            return
        media_id = res.data[0]["id"]
        self._db.table("episodes").delete().eq("media_id", media_id).execute()
        self._db.table("medias").delete().eq("id", media_id).execute()
        log.info(f"🧹 تم تنظيف سجل الميديا لـ: {title}")


# ──────────────────────────────────────────────
# طبقة الخدمات (Service Layer)
# ──────────────────────────────────────────────

class JobProcessor:
    """مسؤول عن تنفيذ مهمة واحدة من البداية للنهاية."""

    def __init__(self, task_repo: TaskRepository, media_repo: MediaRepository, loop):
        self._tasks = task_repo
        self._media = media_repo
        self._loop = loop

    def run(self, job: dict, pyramid_ultimate_beast):
        job_id   = job["id"]
        url      = job["source_url"]
        name     = job.get("task_name", "Unnamed_File")
        trailer  = job.get("trailer_url")

        log.info(f"\n📦 مهمة سحب جديدة ومؤمنة [ID: {job_id}]: {name}")
        log.info(f"⏳ جاري تشغيل المحرك لـ {name}...")

        try:
            self._loop.run_until_complete(
                pyramid_ultimate_beast(url, name, task_id=job_id, meta_data={"trailer_url": trailer})
            )
        except Exception as err:
            self._handle_engine_error(job_id, name, err)

        log.info(f"📡 [Worker]: تم الانتهاء من المعالجة. الاعتماد النهائي تم داخل المحرك.")
        log.info(f"✅ المهمة {job_id} انتهت بالكامل.")
        self._tasks.delete_if_completed(job_id)  # ← هنا
        
    def _handle_engine_error(self, job_id: str, name: str, err: Exception):
        error_msg = str(err)

        # خطأ وهمي بسبب نقل الملف — نتجاهله
        if "No such file or directory" in error_msg and "extracted_" in error_msg:
            log.info("⚠️ تنبيه: المحرك نقل الملف بنجاح ولكن الووركر فقد المسار القديم. سيتم اعتبار المهمة ناجحة.")
            return

        log.error(f"❌ خطأ حقيقي أثناء تشغيل المحرك: {err}")
        try:
            self._media.cleanup_by_title(name)
            self._tasks.mark_failed(job_id, error_msg)
        except Exception as clean_err:
            log.warning(f"⚠️ فشل تنظيف الميديا: {clean_err}")


# ──────────────────────────────────────────────
# طبقة الجدولة (Scheduler / Poll Loop)
# ──────────────────────────────────────────────

class WorkerScheduler:
    """
    مسؤول عن دورة الـ Polling:
    سحب المهام، القفل، التفويض للـ Processor، إدارة وقت الانتظار.
    """

    INITIAL_SLEEP   = 15
    MAX_SLEEP       = 7200  # ساعتان

    def __init__(self, task_repo: TaskRepository, processor: JobProcessor, pyramid_fn):
        self._tasks     = task_repo
        self._processor = processor
        self._pyramid   = pyramid_fn

    def run_forever(self):
        global should_stop_worker
        sleep_time = self.INITIAL_SLEEP

        while not should_stop_worker:
            try:
                jobs = self._tasks.fetch_idle_tasks()

                if jobs:
                    sleep_time = self.INITIAL_SLEEP  # إعادة ضبط وقت الانتظار
                    job = random.choice(jobs)

                    if not self._tasks.try_lock_task(job["id"]):
                        log.info(f"⏭️ المهمة {job['id']} سحبها ووركر تاني حالاً، جاري البحث عن غيرها...")
                        continue

                    self._processor.run(job, self._pyramid)

                else:
                    log.info(f"😴 لا توجد مهام حالياً | النوم: {sleep_time} ثانية")
                    time.sleep(sleep_time)
                    sleep_time = min(sleep_time * 2, self.MAX_SLEEP)

            except Exception as err:
                log.error(f"⚠️ خطأ عام في الـ Worker: {err}")
                self._safe_fail_current_job(err)

        time.sleep(120)

    def _safe_fail_current_job(self, err: Exception):
        """محاولة تعليم المهمة بالفشل إذا كانت متاحة في السياق الحالي."""
        # job_id غير متاح هنا مباشرةً؛ الـ Processor يتعامل معها داخلياً.
        # هذا الـ handler للأخطاء الكارثية خارج دورة المهمة.
        log.warning(f"⚠️ خطأ خارج دورة المهمة: {err}")


# ──────────────────────────────────────────────
# نقطة الدخول (Entry Point)
# ──────────────────────────────────────────────

def ultimate_beast_worker():
    global should_stop_worker
    log.info("⚙️ بدء تشغيل محرك الووركر...")
    should_stop_worker = False

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        from downloader_new.db.supabase_client import supabase as client
        from downloader_new.main_downloader import pyramid_ultimate_beast
        log.info("✅ تم تحميل المكتبات بنجاح من محرك الكور")
    except Exception as e:
        log.error(f"❌ فشل تحميل المكتبات: {e}")
        return

    nest_asyncio.apply()
    log.info(f"🚀 الوحش مستعد في {os.getcwd()} وينتظر الأوامر...")

    task_repo  = TaskRepository(client)
    media_repo = MediaRepository(client)
    processor  = JobProcessor(task_repo, media_repo, loop)
    scheduler  = WorkerScheduler(task_repo, processor, pyramid_ultimate_beast)

    scheduler.run_forever()


if __name__ == "__main__":
    log.info("📌 تم استدعاء الووركر يدوياً.. جاري الإطلاق التجريبي.")
    ultimate_beast_worker()