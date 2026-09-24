# /media/es/DDrive/projects/apps-python/egyPyramid-guardian-ultra/downloader_new/uploaders/uploader_hub.py
import asyncio
import os

# استيراد كائن supabase الجاهز من مجلد db
from downloader_new.db.supabase_client import supabase
from downloader_new.shared.logger import get_beast_logger
from downloader_new.uploaders.others import (
    upload_to_streamtape,
    upload_to_lulustream,
    upload_to_doodstream,
)
from downloader_new.uploaders.vk import upload_to_vk_local
from downloader_new.uploaders.voe import upload_to_voe_api

log = get_beast_logger("GuardianUltra")
lu_key = os.getenv("LULUSTREAM_API_KEY")
st_login = os.getenv("STREAMTAPE_LOGIN")
st_key = os.getenv("STREAMTAPE_KEY")
dood_api_key = os.getenv("DOOD_API_KEY")

async def run_with_timeout(coro, timeout_sec=900):
    try:
        return await asyncio.wait_for(coro, timeout=timeout_sec)
    except asyncio.TimeoutError:
        log.error("⚠️ تجاوزت إحدى السيرفرات الوقت الأقصى (Timeout) وتم إلغاؤها لمنع تجمد السكربت.")
        return None
    except Exception as e:
        log.error(f"⚠️ حدث خطأ أثناء التنفيذ: {e}")
        return None

async def delayed_upload(coro, delay_sec):
    if delay_sec > 0:
        await asyncio.sleep(delay_sec)
    return await coro

async def upload_to_all_servers(
    video_path: str,
    episode_label: str,
    media_id: int,
    episode_id: int,
    remote_source: str,
    task_id,
    final_file_name: str,
) -> dict:
    """
    الرفع المتوازي الخماسي لجميع السيرفرات: VK, Voe, Dood, Streamtape, Lulu.
    تحفظ الروابط الناجحة في Supabase.
    تعيد قاموساً بالمفاتيح: vk_url, voe_watch, voe_download, dood_url, tape_url, lulu_url.
    """
    e_id = episode_id

    if task_id:
        supabase.table("download_tasks").update(
            {
                "status_message": "🚀 ضخ السيرفرات: VK, Voe, Dood, Tape, Lulu",
                "progress_percent": 95,
            }
        ).eq("id", task_id).execute()

    if e_id:
        supabase.table("episodes").update(
            {
                "status_message": "🚀 جاري ضخ الملف لـ VK والرفع المتوازي للبقية...",
                "progress_percent": 90,
            }
        ).eq("id", e_id).execute()

    log.info(f"🚀 البدء في الرفع المتوازي الخماسي (VK + Voe + Dood + Tape + Lulu)...")
    log.info(
        f"remote_source for parallel uploads: {remote_source} | video_path: {video_path}"
    )
    loop = asyncio.get_event_loop()
    task_vk_raw = loop.run_in_executor(None, upload_to_vk_local, episode_label, video_path)
    # تخصيص 20 دقيقة كحد أقصى لرفع VK لكونه رفعاً فعلياً من جهازك
    task_vk = run_with_timeout(task_vk_raw, 1200)

    if remote_source:
        # كل سيرفر سيتم تغليفه بـ 15 دقيقة كحد أقصى (900 ثانية) + وقت تأخير حقيقي لا يوقف السكربت
        task_voe = run_with_timeout(delayed_upload(upload_to_voe_api(video_path, remote_source), 0), 900)
        task_dood = run_with_timeout(delayed_upload(upload_to_doodstream(dood_api_key, remote_source, final_file_name), 15), 900)
        task_tape = run_with_timeout(delayed_upload(upload_to_streamtape(st_login, st_key, remote_source, final_file_name), 30), 900)
        task_lulu = run_with_timeout(delayed_upload(upload_to_lulustream(lu_key, remote_source, final_file_name), 45), 900)
    else:
        task_voe = task_dood = task_tape = task_lulu = run_with_timeout(asyncio.sleep(0, result=None), 5)

    vk_result, file_id, d_url, s_url, lu_url = await asyncio.gather(
        task_vk, task_voe, task_dood, task_tape, task_lulu
    )

    vk_url = vk_result if vk_result else "Failed"
    voe_watch = f"https://voe.sx/e/{file_id}" if file_id else "Failed"

    # حفظ النتائج في Supabase
    if vk_url != "Failed":
        supabase.table("links").upsert(
            {"episode_id": e_id, "server_name": "vk", "url": vk_url},
            on_conflict="episode_id, server_name",
        ).execute()
        log.info(f"✅ VK Link Saved to Supabase!")
    else:
        log.warning(f"⚠️ VK upload failed or returned empty URL.")

    if file_id:
        log.info(f"✅ Voe Saved! ID: {file_id}")
    else:
        log.warning(f"⚠️ Voe upload failed or returned empty ID.")

    if d_url:
        supabase.table("links").upsert(
            {"episode_id": e_id, "server_name": "doodstream", "url": d_url},
            on_conflict="episode_id, server_name",
        ).execute()
        log.info(f"✅ DoodStream Saved!")
    else:
        log.warning(f"⚠️ DoodStream upload failed or returned empty URL.")

    if s_url:
        supabase.table("links").upsert(
            {"episode_id": e_id, "server_name": "streamtape", "url": s_url},
            on_conflict="episode_id, server_name",
        ).execute()
        log.info(f"✅ Streamtape Saved!")
    else:
        log.warning(f"⚠️ Streamtape upload failed or returned empty URL.")

    if lu_url:
        supabase.table("links").upsert(
            {
                "episode_id": e_id,
                "server_name": "lulustream",
                "url": lu_url,
                "last_check_status": "pending",
            },
            on_conflict="episode_id, server_name",
        ).execute()
        log.info(f"✅ LuluStream Saved as pending!")
    else:
        log.warning(f"⚠️ LuluStream upload failed or returned empty URL.")

    return {
        "vk_url": vk_url,
        "voe_watch": voe_watch,
        "dood_url": d_url,
        "tape_url": s_url,
        "lulu_url": lu_url,
    }
