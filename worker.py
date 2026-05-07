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
# سيتم قراءة SUPABASE_URL و SUPABASE_KEY تلقائياً من Environment Variables في السبيس
# 1. تحديد البيئة والمسار آلياً وبدقة
# تم نقل الاستيرادات لداخل الدالة لتجنب تعليق الـ Startup


# 5. دالة التشغيل (باسم عام بدلاً من kaggle_worker)
# 5. دالة التشغيل المحسنة مع تأكيد الجاهزية (Worker Mode)
def ultimate_beast_worker():
    log.info("⚙️ بدء تشغيل محرك الووركر...")

    # 1. إنشاء وتثبيت Event Loop خاص بهذا الـ Thread فوراً
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        from services.supabase_db import SupabaseService
        from downloader.main_downloader import pyramid_ultimate_beast

        log.info("✅ تم تحميل المكتبات بنجاح داخل الـ Thread")
    except Exception as e:
        log.error(f"❌ فشل تحميل المكتبات: {e}")
        return

    nest_asyncio.apply()
    log.info(f"🚀 الوحش مستعد في {os.getcwd()} وينتظر الأوامر...")

    while True:
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
                # التعديل: التأكد من انتظار العملية بالكامل (Await)
                log.info(f"⏳ جاري تشغيل المحرك لـ {file_name}...")
                try:
                    loop.run_until_complete(
                        pyramid_ultimate_beast(url, file_name, task_id=job_id)
                    )
                except Exception as run_err:
                    log.error(f"❌ خطأ أثناء تشغيل المحرك: {run_err}")

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
                        # باقي شروط الـ if كما هي...
                        # 2. التحقق من الشروط المطلوبة
                        if (
                            task_data.get("status") == "completed"
                            and task_data.get("progress_percent") == 100
                        ):

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
            # في حالة الخطأ، لا تترك المهمة عالقة بوضع processing
            try:
                if "job_id" in locals():
                    SupabaseService.client.table("download_tasks").update(
                        {
                            "status": "idle",
                            "status_message": f"❌ فشل الوحش: {str(e)[:100]}",
                        }
                    ).eq("id", job_id).execute()
            except:
                pass
            time.sleep(20)


# تشغيل المحرك
if __name__ == "__main__":
    ultimate_beast_worker()
