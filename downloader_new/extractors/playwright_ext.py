# /media/es/DDrive/projects/apps-python/egyPyramid-guardian-ultra/downloader_new/extractors/playwright_ext.py
import os
from playwright.async_api import async_playwright
import asyncio
import re
from downloader_new.shared.logger import get_beast_logger
from downloader_new.extractors.mixdrop_ext import get_mixdrop_direct_link
from downloader_new.extractors.extract_streamtape import resolve_streamtape
from downloader_new.extractors.doodstream_ext import resolve_doodstream
from downloader_new.extractors.lulustream_ext import resolve_lulustream
from downloader_new.extractors.streamwish_ext import resolve_streamwish
log = get_beast_logger("playwright_ext:")

async def get_direct_link_via_playwright(embed_url, output_path=None):
    file_id = embed_url.split("embed-")[-1].replace(".html", "")
    download_page_url = f"https://down.vidtube.one/d/{file_id}_h"

    log.info(f"🔍 جلب الرابط عبر أمر curl المباشر: {download_page_url}")

    curl_cmd = [
        "curl", "-s", "-L", download_page_url,
        "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "-H", "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "-H", "Accept-Language: en-US,en;q=0.9",
        "-H", "Connection: keep-alive"
    ]

    try:
        # تنفيذ أمر curl بشكل غير متزامن داخل بايثون
        process = await asyncio.create_subprocess_exec(
            *curl_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            log.error(f"❌ خطأ في تنفيذ curl: {stderr.decode('utf-8', errors='ignore')}")
            return None

        html_content = stdout.decode('utf-8', errors='ignore')

        if "Just a moment" in html_content:
            log.error("❌ تم اكتشاف حماية Cloudflare.")
            return None

        # استخراج رابط التحميل المباشر من الـ HTML
        match = re.search(r'class="[^"]*submit-btn[^"]*"[^>]*href="([^"]+)"', html_content)
        if not match:
            match = re.search(r'href="([^"]+)"[^>]*class="[^"]*submit-btn[^"]*"', html_content)

        if not match:
            log.error("❌ لم يتم العثور على زر التحميل المباشر.")
            return None

        direct_link = match.group(1)

        if not direct_link or "http" not in direct_link:
            log.error("❌ الرابط المستخرج غير صالح.")
            return None

        log.info(f"✅ تم صيد الرابط بنجاح: {direct_link[:60]}...")
        return direct_link

    except Exception as e:
        log.error(f"❌ خطأ أثناء تنفيذ عملية curl: {str(e)}")
        return None

async def resolve_direct_url(raw_url: str, output_path: str = None) -> str:
    """يستخرج الرابط المباشر من رابط embed واحد فقط. يرمي Exception لو فشل."""

    if "vidtube.one" in raw_url or "cdn-tube" in raw_url:
        log.info("🎯 VidTube.. جاري الصيد...")
        try:
            # تم حذف تمرير output_path لضمان عدم حدوث تحميل بداخل Playwright
            result = await asyncio.wait_for(
                get_direct_link_via_playwright(raw_url),
                timeout=3600
            )
            if result:
                return result
            raise RuntimeError("فشل صيد VidTube")
        except asyncio.TimeoutError:
            raise RuntimeError("Timeout: VidTube")

    elif "mixdrop" in raw_url:
        log.info("🎯 MixDrop.. جاري الصيد...")
        try:
            direct_link = await asyncio.wait_for(get_mixdrop_direct_link(raw_url), timeout=240)
            if direct_link == "404_DELETED":
                raise RuntimeError("💀 MixDrop: الملف محذوف")
            if direct_link:
                return direct_link
            raise RuntimeError("فشل صيد MixDrop")
        except asyncio.TimeoutError:
            raise RuntimeError("Timeout: MixDrop")

    elif "streamtape" in raw_url or "stape" in raw_url or "shstream" in raw_url:
        log.info("🎯 Streamtape.. جاري الصيد...")
        try:
            direct_link = await asyncio.wait_for(resolve_streamtape(raw_url), timeout=120)
            if direct_link == "404_DELETED":
                raise RuntimeError("💀 Streamtape: الملف محذوف")
            if direct_link:
                return direct_link
            raise RuntimeError("فشل صيد Streamtape")
        except asyncio.TimeoutError:
            raise RuntimeError("Timeout: Streamtape")

    elif "doodstream" in raw_url or "playmogo" in raw_url or "d0o0d" in raw_url:
        log.info("🎯 Doodstream.. جاري الصيد...")
        try:
            direct_link = await asyncio.wait_for(resolve_doodstream(raw_url), timeout=120)
            if direct_link == "404_DELETED":
                raise RuntimeError("💀 Doodstream: الملف محذوف")
            if direct_link:
                return direct_link
            raise RuntimeError("فشل صيد Doodstream")
        except asyncio.TimeoutError:
            raise RuntimeError("Timeout: Doodstream")

    elif "lulustream" in raw_url or "luluvdo" in raw_url:
        log.warning("⏭️ تخطي LuluStream مؤقتاً بناءً على الطلب (زر التحميل غير ظاهر).")
        raise RuntimeError("تخطي LuluStream مؤقتاً")
        
    elif "streamwish" in raw_url:
        direct_link = await asyncio.wait_for(resolve_streamwish(raw_url), timeout=120)
        if direct_link == "404_DELETED":
            raise RuntimeError("💀 StreamWish: الملف محذوف")
        if direct_link:
            return direct_link
        raise RuntimeError("فشل صيد StreamWish")
    # رابط مباشر مش محتاج استخراج
    return raw_url