# /media/es/DDrive/projects/apps-python/egyPyramid-guardian-ultra/worker.py
import sys
import os
import time
import random
import nest_asyncio
import asyncio
from downloader.logger_setup import get_beast_logger

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
        from services.supabase_db import SupabaseService
        # بننادي على الوحش من ملف الكور مباشرة لأنه هو اللي فيه الدالة الحقيقية دلوقتى
        try:
            from downloader.core_engine import pyramid_ultimate_beast
        except ImportError:
            from downloader.main_downloader import pyramid_ultimate_beast

        log.info("✅ تم تحميل المكتبات بنجاح من محرك الكور")
    except Exception as e:
        log.error(f"❌ فشل تحميل المكتبات: {e}")
        return

    nest_asyncio.apply()
    log.info(f"🚀 الوحش مستعد في {os.getcwd()} وينتظر الأوامر...")

    while not should_stop_worker:
        # فحص إضافي للتأكد
        if should_stop_worker:
            break

        # كود سحب المهام (fetch tasks)...
        try:

            # 1. سحب المهمة (الأقدم أولاً)
            # جلب أول 5 مهام متاحة بدل واحدة فقط
            pending_res = (
                SupabaseService.client.table("download_tasks")
                .select("*")
                .eq("status", "idle")
                .order("created_at", desc=False)
                .limit(5)
                .execute()
            )

            if pending_res.data:
                # اختيار مهمة عشوائية من الـ 5 لضمان عدم تصادم الـ 3 تبويبات
                job = random.choice(pending_res.data)
                job_id = job["id"]
                url = job["source_url"]
                file_name = job.get("task_name", "Unnamed_File")

                # محاولة "قفل" المهمة (Lock): لا يحدث التحديث إلا لو كانت الحالة لا تزال idle
                lock_res = (
                    SupabaseService.client.table("download_tasks")
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
                    if "No such file or directory" in error_msg and "extracted_" in error_msg:
                        log.info("⚠️ تنبيه: المحرك نقل الملف بنجاح ولكن الووركر فقد المسار القديم. سيتم اعتبار المهمة ناجحة.")
                    else:
                        log.error(f"❌ خطأ حقيقي أثناء تشغيل المحرك: {run_err}")
                        # --- 🧹 تنظيف الأشباح فقط في حالة الخطأ الحقيقي ---
                        try:
                            media_res = SupabaseService.client.table("medias").select("id").ilike("title", f"%{file_name}%").limit(1).execute()
                            if media_res.data:
                                m_id = media_res.data[0]["id"]
                                SupabaseService.client.table("episodes").delete().eq("media_id", m_id).execute()
                                SupabaseService.client.table("medias").delete().eq("id", m_id).execute()
                                log.info(f"🧹 تم تنظيف سجل الميديا لـ: {file_name}")

                            SupabaseService.client.table("download_tasks").update({
                                "status": "failed",
                                "status_message": f"❌ فشل: {error_msg[:50]}",
                            }).eq("id", job_id).execute()
                        except Exception as clean_err:
                            log.warning(f"⚠️ فشل تنظيف الميديا: {clean_err}")
                        

                # --- [هام جداً]: لا تضع أي أكواد تحديث "Success" هنا إلا لو كنت متأكد إن الدالة رجعت بنجاح ---

                # --- ⚡ [سطر الأمان النهائي]: تم نقل الاعتماد لمحرك المعالجة ⚡ ---
                log.info(
                    f"📡 [Worker]: تم الانتهاء من المعالجة. الاعتماد النهائي تم داخل المحرك."
                )
                # --- 🗑️ [منطق حذف المهمة المكتملة] ---
                try:
                    # 1. جلب حالة المهمة الحالية للتأكد من اكتمالها فعلياً
                    # استبدل هذا الجزء داخل كود الحذف:
                    check_task = (
                        SupabaseService.client.table("download_tasks")
                        .select("status", "progress_percent", "status_message")
                        .eq("id", job_id)
                        .limit(1)  # أضمن من single في بعض الحالات
                        .execute()
                    )

                    if check_task.data and len(check_task.data) > 0:
                        task_data = check_task.data[0]
                        current_status = task_data.get("status")
                        
                        # لو الحالة completed (تمت بنجاح) أو failed (فشلت تماماً)
                        # في الحالتين لازم نحذفها عشان ما تتكررش
                        if current_status in ["completed", "failed"]:
                            log.info(f"🧹 تنظيف: المهمة {job_id} انتهت بحالة ({current_status})، جاري حذفها...")
                            SupabaseService.client.table("download_tasks").delete().eq("id", job_id).execute()
                            log.info(f"🗑️ تم حذف المهمة {job_id} من قائمة الانتظار.")

                            log.info(
                                f"🧹 تنظيف: المهمة {job_id} اكتملت بنجاح، جاري حذفها من الجدول..."
                            )

                            # 3. الحذف من جدول download_tasks
                            SupabaseService.client.table("download_tasks").delete().eq(
                                "id", job_id
                            ).execute()
                            log.info(f"🗑️ تم حذف المهمة {job_id} بنجاح.")
                except Exception as del_err:
                    log.error(f"⚠️ خطأ أثناء محاولة حذف المهمة: {del_err}")
                # --- ⚡ [سطر الأمان النهائي]: تأكيد الجاهزية من الـ Worker ⚡ ---
                log.info(f"✅ المهمة {job_id} انتهت بالكامل.")

            else:
                # استبدال النقطة بلوج رسمي عشان يظهر في Hugging Face فوراً
                log.info(
                    "😴 الوحش يبحث في الداتابيز.. لا توجد مهام حالياً (status: idle)"
                )
                time.sleep(15)

        except Exception as e:
            log.error(f"⚠️ خطأ في الـ Worker: {e}")
            # في حالة الخطأ العام، نعيد المهمة لـ idle لتجربتها لاحقاً أو تعليمها بالفشل
            try:
                if "job_id" in locals():
                    SupabaseService.client.table("download_tasks").update(
                        {
                            "status": "failed",  # تغيير لـ failed أفضل عشان ميدخلش في Loop لا نهائي لو الرابط ميت
                            "status_message": f"❌ خطأ فني بالووركر: {str(e)[:100]}",
                        }
                    ).eq("id", job_id).execute()
            except:
                pass
            time.sleep(20)
# تشغيل المحرك
if __name__ == "__main__":
    ultimate_beast_worker()
