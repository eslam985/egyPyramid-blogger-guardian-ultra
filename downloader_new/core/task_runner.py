# /media/es/DDrive/projects/apps-python/egyPyramid-guardian-ultra/downloader_new/core/task_runner.py
import os
from downloader_new.shared.logger import get_beast_logger
from downloader_new.db.supabase_client import supabase, save_to_supabase
from downloader_new.uploaders.telegram import send_to_telegram
from downloader_new.uploaders.others import upload_to_mixdrop

log = get_beast_logger("GuardianUltra")
mix_user = os.getenv("MIXDROP_EMAIL")
mix_key = os.getenv("MIXDROP_API_KEY")


# 4. الدوال الوسيطة
async def run_pyramid_tasks(task_list):
    """دالة وسيطة لاستدعاء المايسترو لتجنب الـ Circular Import"""
    from downloader_new.main_downloader import run_pyramid_tasks as original_run
    return await original_run(task_list)


async def finalize_episode(
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
    """
    إنهاء معالجة الحلقة: رفع MixDrop، التحديث النهائي في Supabase،
    التحقق من الجودة، إطلاق الجاهزية، إرسال تليجرام،
    إغلاق التاسك، حذف الملف المحلي، تحديث حالة الحلقة.
    """
    e_id = episode_id
    voe_watch = upload_results.get("voe_watch", "Failed")
    vk_url = upload_results.get("vk_url", "Failed")

    # --- 9. الرفع لـ MixDrop ---
    try:
        if e_id:
            supabase.table("episodes").update(
                {
                    "status_message": "💧 جاري الرفع لـ MixDrop...",
                    "progress_percent": 99,
                }
            ).eq("id", e_id).execute()

        mix_url = await upload_to_mixdrop(video_path, mix_user, mix_key)
        log.info(f"mix_url: {mix_url}")
        if mix_url:
            supabase.table("links").upsert(
                {"episode_id": e_id, "server_name": "mixdrop", "url": mix_url},
                on_conflict="episode_id, server_name",
            ).execute()
            log.info(f"✅ تم رفع وحفظ رابط MixDrop: {mix_url}")
    except Exception as e:
        log.warning(f"⚠️ فشل MixDrop: {e}")

    # --- 10. التحديث النهائي الشامل ---
    try:
        save_res = save_to_supabase(
            voe_watch,
            vk_url,
            loop_display_title,
            original_task_name,
            meta_story,
            final_poster,
            meta_year,
            meta_rating,
            video_path,
            archive_url,
            tmdb_id=tmdb_data["tmdb_id"],
            labels=meta_labels,
            runtime=meta_runtime,
            duration_iso=meta_duration,
        )
    except Exception as e:
        log.error(f"❌ فشل التحديث النهائي في سوبابيز: {e}")
        save_res = None

    if save_res:
        e_id, media_id, meta_story, final_poster = save_res
        log.info(f"🏁 تم إغلاق المهمة بنجاح وحفظ كافة البيانات.")

        row_data_for_tg = {
            "title": loop_display_title,
            "story": meta_story if meta_story else "لا يوجد وصف متاح حالياً.",
            "poster_url": final_poster,
            "labels": meta_labels,
            "year": meta_year,
        }

        status = send_to_telegram(
            row=row_data_for_tg,
            content_type=category,
            action_text="المشاهدة",
            post_url=final_poster,
            lang_val="لغة أصلية (مترجم)",
        )

        if status:
            log.info(f"✅ كولاب أرسل تمبلت تليجرام بنجاح")

        quality_pass = False
        has_metadata = False
        if media_id:
            link_check = (
                supabase.table("links")
                .select("id", count="exact")
                .eq("episode_id", e_id)
                .execute()
            )
            links_count = link_check.count if link_check.count is not None else 0

            has_metadata = bool(meta_story and meta_story.strip()) and bool(
                final_poster and final_poster.strip()
            )

            if links_count >= 3:
                quality_pass = True
                if has_metadata:
                    supabase.table("medias").update({"is_ready": True}).eq(
                        "id", media_id
                    ).execute()
                    log.info(
                        f"🚀 تم إطلاق إشارة الجاهزية الكاملة (سيرفرات: {links_count})"
                    )
                else:
                    log.warning(
                        f"🟡 تم الحفظ بنجاح ولكن بدون جاهزية (نقص في الصورة أو الوصف)"
                    )
            else:
                quality_pass = False

        if task_id:
            try:
                if media_id and not quality_pass:
                    supabase.table("medias").delete().eq("id", media_id).execute()
                    log.warning(f"🗑️ تم حذف الميديا لعدم وجود روابط كافية.")
                    final_status, final_msg = "failed", "❌ فشل: السيرفرات أقل من 3"
                else:
                    final_status = "completed"
                    final_msg = (
                        "✅ اكتملت بنجاح!"
                        if has_metadata
                        else "⚠️ اكتملت (بدون بيانات وصفية)"
                    )

                supabase.table("download_tasks").update(
                    {
                        "status": final_status,
                        "progress_percent": 100,
                        "status_message": final_msg,
                    }
                ).eq("id", task_id).execute()
                log.info(f"✅ تم إغلاق التاسك {task_id} بحالة: {final_status}")
            except Exception as task_err:
                log.error(f"❌ فشل تحديث حالة التاسك في سوبابيز: {task_err}")
            else:
                msg = (
                    "✅ اكتملت بنجاح!"
                    if has_metadata
                    else "⚠️ اكتملت بنجاح (يرجى إضافة الصورة والوصف يدوياً)"
                )
                supabase.table("download_tasks").update(
                    {
                        "status": "completed",
                        "progress_percent": 100,
                        "status_message": msg,
                    }
                ).eq("id", task_id).execute()

    # تنظيف الملف المحلي
    if os.path.exists(video_path):
        try:
            os.remove(video_path)
            log.info(f"🗑️ تم تنظيف الملف المحلي: {os.path.basename(video_path)}")
        except Exception as e:
            log.warning(f"⚠️ لم يتم مسح الملف المؤقت: {e}")

    # تحديث الحالة النهائية للحلقة
    try:
        supabase.table("episodes").update(
            {
                "progress_percent": 100,
                "status_message": "✅ اكتملت المعالجة والرفع بنجاح",
                "download_speed": "Done",
            }
        ).eq("id", e_id).execute()
    except:
        pass
