# /media/es/DDrive/projects/apps-python/egyPyramid-guardian-ultra/downloader_new/media/downloader.py
import os 
import asyncio
import time
import re
# استيراد كائن supabase الجاهز من مجلد db
from downloader_new.db.supabase_client import supabase
from downloader_new.shared.logger import get_beast_logger
log = get_beast_logger("GuardianUltra")

def build_ytdlp_command(url: str, output_template: str, smart_headers: list) -> list:
    """
    بناء قائمة أوامر yt-dlp الكاملة مع كل الخيارات.
    تعيد القائمة الجاهزة لـ asyncio.create_subprocess_exec.
    """
    if "mixdrop" in url or "miixdrop" in url:
        url = re.sub(r'https?://(www\.)?[a-zA-Z0-9\-]+\.[a-zA-Z]+/e/', 'https://mixdrop.co/e/', url)

    cmd = [
        "yt-dlp",
        "-v",
        "--no-playlist",
        "--geo-bypass",
        "--user-agent",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "--add-header",
        "Accept: video/webp,video/apng,video/*,*/*;q=0.8",
        "--add-header",
        "Accept-Language: en-US,en;q=0.9,ar;q=0.8",
        "--no-check-certificate",
        "--retries",
        "infinite",
        "--socket-timeout",
        "120",
        "--concurrent-fragments",
        "10",
        "--file-access-retries",
        "infinite",
        "--fragment-retries",
        "infinite",
        "--hls-use-mpegts",
    ]
    # دمج هيدرز الخداع من الـ Cookbook
    cmd.extend(smart_headers)

    if "lulu" in url:
        cmd.extend(["--referer", "https://topcinemaa.com/"])

    if "vidtube" in url or "cdn-tube" in url:
        cmd.extend(["--extractor-args", "jwplayer:base-url=https://vidtube.one/"])

    cmd.extend(
        [
            "-f",
            "(bestvideo[width<=720][height<=1280]/bestvideo[height<=720][width<=1280]+bestaudio/best[width<=720][height<=1280]/best[height<=720][width<=1280]) / "
            "(bestvideo[width<=1080][height<=1920][filesize<1950M]+bestaudio/best[width<=1080][height<=1920][filesize<1950M]) / "
            "best",
            "--merge-output-format",
            "mp4",
            "--max-filesize",
            "1950M",
            "--post-overwrites",
            "--no-check-certificate",
            "--newline",
            f"{url}",
            "-o",
            output_template,
        ]
    )

    return cmd


async def download_video(cmd: list, task_id, display_title: str, extract_dir: str):
    """
    تنفيذ عملية التحميل باستخدام asyncio، مع تتبع التقدم وتحديث قاعدة البيانات كل 15 ثانية.
    تعيد المسار الكامل للملف المحمّل، أو None إذا فشل.
    """
    process = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
    )

    last_db_update = 0
    last_percent_log = -1

    while True:
        line = await process.stdout.readline()
        if not line:
            break
        line_str = line.decode().strip()

        progress_match = re.search(
            r"\[download\]\s+(\d+\.\d+)%\s+of\s+([\d\w\.]+)(?:\s+at\s+([\d\w\./s]+))?(?:\s+ETA\s+([\d:]+))?",
            line_str,
        )

        if progress_match:
            percent = progress_match.group(1)
            total = progress_match.group(2)
            speed = progress_match.group(3) or "---"
            eta = progress_match.group(4) or "--:--"
            percent_int = int(float(percent))
            now = time.time()
            if percent_int % 5 == 0 and percent_int != last_percent_log:
                log.info(
                    f"📥 {display_title[:15]}.. | {percent_int}% of {total} | ⚡ {speed} | ⏳ ETA: {eta}"
                )
                last_percent_log = percent_int

            if task_id and (now - last_db_update > 15):
                try:
                    supabase.table("download_tasks").update(
                        {
                            "progress_percent": percent_int,
                            "status_message": f"📥 جاري التحميل: {percent_int}%",
                            "download_speed": speed,
                        }
                    ).eq("id", task_id).execute()
                    last_db_update = now
                except:
                    pass
        elif any(x in line_str.upper() for x in ["ERROR", "WARNING", "FAILED"]):
            log.info(f"\n⚠️ ALERT_LOG: {line_str}")

    print("")
    await process.wait()

    if process.returncode != 0:
        if (
            extract_dir
            and os.path.exists(extract_dir)
            and any(
                os.path.isfile(os.path.join(extract_dir, f))
                for f in os.listdir(extract_dir)
            )
        ):
            log.info(
                f"✅ تم تجاوز خطأ المحرك (Code: {process.returncode}) - الملفات موجودة."
            )
        else:
            log.error(f"❌ فشل محرك التحميل! كود الخطأ: {process.returncode}")

    await asyncio.sleep(5)
    actual_downloaded_path = None
    
    search_locations = [extract_dir, os.getcwd()]

    for loc in search_locations:
        if not os.path.exists(loc):
            continue

        all_files = [os.path.join(loc, f) for f in os.listdir(loc)]
        actual_files = [
            f
            for f in all_files
            if os.path.isfile(f)
            and not f.endswith((".part", ".ytdl", ".temp", ".txt", ".md"))
        ]

        if actual_files:
            actual_files.sort(key=os.path.getmtime, reverse=True)
            actual_downloaded_path = actual_files[0]
            break

    if actual_downloaded_path:
        log.info(f"✅ تم اكتمال التحميل الفعلي: {actual_downloaded_path}")
    else:
        log.error(
            f"❌ فشل التحميل: المجلد فارغ! المحتوى الموجود: {os.listdir(extract_dir) if os.path.exists(extract_dir) else 'المجلد غير موجود'}"
        )

    return actual_downloaded_path
