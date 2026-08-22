import os
import asyncio
import time
import re

from downloader_new.db.supabase_client import supabase
from downloader_new.shared.logger import get_beast_logger

log = get_beast_logger("downloader.py")

# ──────────────────────────────────────────────
# Helpers / URL Utils
# ──────────────────────────────────────────────

def is_direct_cdn_link(url: str) -> bool:
    """يكشف إذا كان الرابط مباشراً من CDN بدون حاجة لاستخراج."""
    return "cdn-video.xyz" in url or "serv-stream-cdn" in url


def _normalize_mixdrop_url(url: str) -> str:
    """يوحّد روابط MixDrop على دومين miixdrop.net."""
    return re.sub(
        r"https?://(www\.)?[a-zA-Z0-9\-]+\.[a-zA-Z]+/(e|f)/",
        r"https://miixdrop.net/\2/",
        url,
    )


# ──────────────────────────────────────────────
# Command Builders
# ──────────────────────────────────────────────

COMMON_HEADERS = [
    "--user-agent",
    "Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Mobile Safari/537.36",
    "--add-header", "Accept: video/webp,video/apng,video/*,*/*;q=0.8",
    "--add-header", "Accept-Language: en-US,en;q=0.9,ar;q=0.8",
]

FORMAT_SELECTOR = (
    "(bestvideo[width<=720][height<=1280]/bestvideo[height<=720][width<=1280]+bestaudio"
    "/best[width<=720][height<=1280]/best[height<=720][width<=1280]) / "
    "(bestvideo[width<=1080][height<=1920][filesize<1950M]+bestaudio"
    "/best[width<=1080][height<=1920][filesize<1950M]) / best"
)


def build_curl_command(url: str, output_path: str) -> list:
    """أمر curl للروابط المباشرة من CDN."""
    return [
        "curl", "-L", "-g",
        "--retry", "5",
        "--retry-delay", "3",
        "--max-time", "3600",
        "-H", "Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Mobile Safari/537.36",
        "-H", "Referer: https://down.vidtube.one/",
        "-H", "Origin: https://down.vidtube.one",
        "-H", "Accept: video/webp,video/apng,video/*,*/*;q=0.8",
        "-o", output_path,
        url,
    ]


def build_ytdlp_command(url: str, output_template: str, smart_headers: list) -> list:
    """يبني أمر yt-dlp الكامل بكل الخيارات والهيدرز المناسبة للرابط."""
    if "mixdrop" in url or "miixdrop" in url:
        url = _normalize_mixdrop_url(url)

    cmd = [
        "yt-dlp", "-v",
        "--no-playlist",
        "--geo-bypass",
        *COMMON_HEADERS,
        "--no-check-certificate",
        "--retries", "infinite",
        "--socket-timeout", "120",
        "--concurrent-fragments", "10",
        "--file-access-retries", "infinite",
        "--fragment-retries", "infinite",
        "--hls-use-mpegts",
        *smart_headers,
    ]

    if "lulu" in url:
        cmd.extend(["--referer", "https://topcinemaa.com/"])

    if "vidtube" in url or "cdn-tube" in url:
        cmd.extend(["--extractor-args", "jwplayer:base-url=https://vidtube.one/"])

    if "cdn-video.xyz" in url or "serv-stream-cdn" in url:
        cmd.extend([
            "--referer", "https://down.vidtube.one/",
            "--add-header", "Origin: https://down.vidtube.one",
        ])

    cmd.extend([
        "-f", FORMAT_SELECTOR,
        "--merge-output-format", "mp4",
        "--max-filesize", "1950M",
        "--post-overwrites",
        "--no-check-certificate",
        "--newline",
        url,
        "-o", output_template,
    ])

    return cmd


# ──────────────────────────────────────────────
# Progress Tracker
# ──────────────────────────────────────────────

class DownloadProgressTracker:
    """يتابع تقدم yt-dlp ويحدّث قاعدة البيانات كل 15 ثانية."""

    DB_UPDATE_INTERVAL = 15  # ثانية

    def __init__(self, task_id, display_title: str):
        self._task_id = task_id
        self._title = display_title
        self._last_db_update = 0
        self._last_percent_log = -1

    def parse_and_report(self, line: str):
        match = re.search(
            r"\[download\]\s+(\d+\.\d+)%\s+of\s+([\d\w\.]+)"
            r"(?:\s+at\s+([\d\w\./s]+))?(?:\s+ETA\s+([\d:]+))?",
            line,
        )
        if not match:
            return

        percent_int = int(float(match.group(1)))
        total       = match.group(2)
        speed       = match.group(3) or "---"
        eta         = match.group(4) or "--:--"

        if percent_int % 5 == 0 and percent_int != self._last_percent_log:
            log.info(f"📥 {self._title[:15]}.. | {percent_int}% of {total} | ⚡ {speed} | ⏳ ETA: {eta}")
            self._last_percent_log = percent_int

        self._maybe_update_db(percent_int, speed)

    def _maybe_update_db(self, percent: int, speed: str):
        if not self._task_id:
            return
        now = time.time()
        if now - self._last_db_update < self.DB_UPDATE_INTERVAL:
            return
        try:
            supabase.table("download_tasks").update({
                "progress_percent": percent,
                "status_message": f"📥 جاري التحميل: {percent}%",
                "download_speed": speed,
            }).eq("id", self._task_id).execute()
            self._last_db_update = now
        except Exception:
            pass


# ──────────────────────────────────────────────
# File Finder
# ──────────────────────────────────────────────

class DownloadedFileFinder:
    """يبحث عن الملف الفعلي المحمّل في المجلدات المحتملة."""

    IGNORED_EXTENSIONS = (".part", ".ytdl", ".temp", ".txt", ".md")

    def find(self, *search_dirs: str) -> str | None:
        for directory in search_dirs:
            if not os.path.exists(directory):
                continue
            candidates = [
                os.path.join(directory, f)
                for f in os.listdir(directory)
                if os.path.isfile(os.path.join(directory, f))
                and not f.endswith(self.IGNORED_EXTENSIONS)
            ]
            if candidates:
                candidates.sort(key=os.path.getmtime, reverse=True)
                return candidates[0]
        return None


# ──────────────────────────────────────────────
# Downloaders
# ──────────────────────────────────────────────

async def download_video_curl(cmd: list, display_title: str, extract_dir: str, direct_url: str = None) -> str | None:
    """تحميل مباشر بـ httpx للروابط CDN."""
    import httpx

    if not direct_url:
        return None

    output_path = cmd[cmd.index("-o") + 1]
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Mobile Safari/537.36",
        "Referer": "https://down.vidtube.one/",
        "Origin": "https://down.vidtube.one",
    }

    log.info(f"⬇️ httpx جاري التحميل: {display_title[:20]}...")
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=3600) as client:
            async with client.stream("GET", direct_url, headers=headers) as response:
                log.info(f"📡 HTTP Status: {response.status_code}")
                if response.status_code != 200:
                    raise RuntimeError(f"فشل httpx: HTTP {response.status_code}")

                total = int(response.headers.get("content-length", 0))
                downloaded = 0

                with open(output_path, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=1024 * 1024):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total and int(downloaded / total * 100) % 10 == 0:
                            log.info(f"📥 {display_title[:15]}.. | {downloaded/total*100:.0f}%")

        file_size = os.path.getsize(output_path)
        if file_size < 1_000_000:
            os.remove(output_path)
            raise RuntimeError(f"الملف المحمّل صغير جداً ({file_size} bytes) — يُعدّ فاشلاً")

        log.info(f"✅ httpx اكتمل: {output_path} ({file_size/1_000_000:.1f} MB)")
        return output_path

    except Exception as e:
        log.error(f"❌ خطأ httpx: {e}")
        raise


async def download_video(cmd: list, task_id, display_title: str, extract_dir: str) -> str:
    """
    ينفّذ yt-dlp ويتابع التقدم.
    يُرجع مسار الملف المحمّل.
    يرمي RuntimeError إذا فشل التحميل فعلاً.
    """
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )

    tracker = DownloadProgressTracker(task_id, display_title)

    async for raw_line in process.stdout:
        line = raw_line.decode().strip()
        tracker.parse_and_report(line)

        if any(x in line.upper() for x in ["ERROR", "WARNING", "FAILED"]):
            log.warning(f"⚠️ ALERT_LOG: {line}")

    await process.wait()
    await asyncio.sleep(5)  # انتظار كتابة الملف على الديسك

    # ── التحقق من وجود الملف أولاً حتى لو returncode != 0 ──
    finder = DownloadedFileFinder()
    found  = finder.find(extract_dir, os.getcwd())

    if found:
        log.info(f"✅ تم اكتمال التحميل الفعلي: {found}")
        return found

    # ── لا يوجد ملف = فشل حقيقي ──
    dir_contents = os.listdir(extract_dir) if os.path.exists(extract_dir) else "المجلد غير موجود"
    error_msg = (
        f"فشل التحميل (exit code: {process.returncode}) — "
        f"المجلد فارغ. المحتوى: {dir_contents}"
    )
    log.error(f"❌ {error_msg}")
    raise RuntimeError(error_msg)