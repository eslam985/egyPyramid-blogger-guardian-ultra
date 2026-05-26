# /media/es/DDrive/projects/apps-python/egyPyramid-guardian-ultra/worker.py
import os
import time
import random
import nest_asyncio
import asyncio
from downloader_new.shared.logger import get_beast_logger

# في Hugging Face المشروع في الجذر دائماً
PROJECT_ROOT = os.getcwd()
log = get_beast_logger("GuardianWorker")

log.info(f"🚀 تم تشغيل الووركر بنجاح من المسار: {PROJECT_ROOT}")

should_stop_worker = False


def ultimate_beast_worker():
    global should_stop_worker
    log.info("⚙️ بدء تشغيل محرك الووركر...")

    # تأكد من تصفير الحالة عند كل تشغيل جديد
    should_stop_worker = False

    # 1. إنشاء وتثبيت Event Loop خاص بهذا الـ Thread فوراً
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

    current_sleep = 15
    while not should_stop_worker:
        # فحص إضافي للتأكد
        if should_stop_worker:
            break

        # كود سحب المهام (fetch tasks)...
        try:

            # 1. سحب المهمة (الأقدم أولاً)
            # جلب أول 5 مهام متاحة بدل واحدة فقط
            pending_res = (
                client.table("download_tasks")
                .select("*")
                .eq("status", "idle")
                .order("created_at", desc=False)
                .limit(5)
                .execute()
            )

            if pending_res.data:
                current_sleep = 15
                # اختيار مهمة عشوائية من الـ 5 لضمان عدم تصادم الـ 3 تبويبات
                job = random.choice(pending_res.data)
                job_id = job["id"]
                url = job["source_url"]
                file_name = job.get("task_name", "Unnamed_File")

                # محاولة "قفل" المهمة (Lock): لا يحدث التحديث إلا لو كانت الحالة لا تزال idle
                lock_res = (
                    client.table("download_tasks")
                    .update(
                        {
                            "status": "processing",
                            "status_message": "🚀 الوحش بدأ السحب والتحليل...",
                            "progress_percent": 5,
                        }
                    )
                    .eq("id", job_id)
                    .eq("status", "idle")
                    .execute()
                )

                # لو التحديث مرجعش بيانات، ده معناه إن ووركر تاني سبقك وقفلها في نفس الثانية
                if not lock_res.data:
                    log.info(
                        f"⏭️ المهمة {job_id} سحبها ووركر تاني حالا، جاري البحث عن غيرها..."
                    )
                    continue

                log.info(f"\n📦 مهمة سحب جديدة ومؤمنة [ID: {job_id}]: {file_name}")

                # --- نهاية التعديل المحصن ---

                # 3. تشغيل الوحش (pyramid_ultimate_beast)
                # 3. تشغيل الوحش (pyramid_ultimate_beast)
                log.info(f"⏳ جاري تشغيل المحرك لـ {file_name}...")
                try:
                    loop.run_until_complete(
                        pyramid_ultimate_beast(url, file_name, task_id=job_id)
                    )
                except Exception as run_err:
                    # مراجعة الخطأ: لو الخطأ بسبب إن الملف مش موجود (لأننا نقلناه)، نتجاهله
                    error_msg = str(run_err)
                    if (
                        "No such file or directory" in error_msg
                        and "extracted_" in error_msg
                    ):
                        log.info(
                            "⚠️ تنبيه: المحرك نقل الملف بنجاح ولكن الووركر فقد المسار القديم. سيتم اعتبار المهمة ناجحة."
                        )
                    else:
                        log.error(f"❌ خطأ حقيقي أثناء تشغيل المحرك: {run_err}")
                        # --- 🧹 تنظيف الأشباح فقط في حالة الخطأ الحقيقي ---
                        try:
                            media_res = (
                                client.table("medias")
                                .select("id")
                                .ilike("title", f"%{file_name}%")
                                .limit(1)
                                .execute()
                            )
                            if media_res.data:
                                m_id = media_res.data[0]["id"]
                                client.table("episodes").delete().eq(
                                    "media_id", m_id
                                ).execute()
                                client.table("medias").delete().eq("id", m_id).execute()
                                log.info(f"🧹 تم تنظيف سجل الميديا لـ: {file_name}")

                            client.table("download_tasks").update(
                                {
                                    "status": "failed",
                                    "status_message": f"❌ فشل: {error_msg[:50]}",
                                }
                            ).eq("id", job_id).execute()
                        except Exception as clean_err:
                            log.warning(f"⚠️ فشل تنظيف الميديا: {clean_err}")

                # --- [هام جداً]: لا تضع أي أكواد تحديث "Success" هنا إلا لو كنت متأكد إن الدالة رجعت بنجاح ---

                # --- ⚡ [سطر الأمان النهائي]: تم نقل الاعتماد لمحرك المعالجة ⚡ ---
                log.info(
                    f"📡 [Worker]: تم الانتهاء من المعالجة. الاعتماد النهائي تم داخل المحرك."
                )
                # --- 🗑️ [منطق حذف المهمة المكتملة] ---
                # --- 🗑️ تنظيف المهمة بعد الانتهاء ---
                try:
                    task_check = (
                        client.table("download_tasks")
                        .select("status")
                        .eq("id", job_id)
                        .execute()
                    )
                    if task_check.data and task_check.data[0]["status"] in [
                        "completed",
                        "failed",
                    ]:
                        client.table("download_tasks").delete().eq(
                            "id", job_id
                        ).execute()
                        log.info(f"🗑️ تم تنظيف وحذف المهمة {job_id} من الجدول.")
                except Exception as del_err:
                    log.error(f"⚠️ خطأ أثناء حذف المهمة: {del_err}")
                # --- ⚡ [سطر الأمان النهائي]: تأكيد الجاهزية من الـ Worker ⚡ ---
                log.info(f"✅ المهمة {job_id} انتهت بالكامل.")

            else:
                log.info(
                    f"😴 الوحش يبحث في الداتابيز.. لا توجد مهام حالياً (status: idle) | النوم الحالي: {current_sleep} ثانية"
                )
                time.sleep(current_sleep)
                # مضاعفة الوقت للمرة القادمة بشرط ألا يتخطى ساعتين (7200 ثانية)
                current_sleep = min(current_sleep * 2, 7200)

        except Exception as e:
            log.error(f"⚠️ خطأ في الـ Worker: {e}")
            # في حالة الخطأ العام، نعيد المهمة لـ idle لتجربتها لاحقاً أو تعليمها بالفشل
            try:
                if "job_id" in locals():
                    client.table("download_tasks").update(
                        {
                            "status": "failed",  # تغيير لـ failed أفضل عشان ميدخلش في Loop لا نهائي لو الرابط ميت
                            "status_message": f"❌ خطأ فني بالووركر: {str(e)[:100]}",
                        }
                    ).eq("id", job_id).execute()
            except:
                pass
            time.sleep(20)


# أمان التشغيل السحابي المباشر
if __name__ == "__main__":
    log.info("📌 تم استدعاء الووركر يدوياً.. جاري الإطلاق التجريبي.")
    ultimate_beast_worker()
