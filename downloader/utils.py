
# Utility Functions Layer (Headers, Formatting, etc.)
import random
# استيراد اللوجر عشان لو حبيت تسجل أي خطأ في جلب الهيدرز
try:
    from .logger_setup import get_beast_logger
except ImportError:
    import os
    import sys
    sys.path.append(os.path.dirname(__file__))
    from logger_setup import get_beast_logger

log = get_beast_logger("GuardianUltra")
# قائمة "الخداع" للمواقع المختلفة - ضعها في أعلى الملف
SITES_COOKBOOK = {
    "vod3": {
        "Referer": "https://vod3.cf.dmcdn.net/",
        "Origin": "https://vod3.cf.dmcdn.net/",
    },
    "topcinema": {
        "Referer": "https://topcinema.rip/",
        "Origin": "https://topcinema.rip",
    },
    "vidtube": {
        "Referer": "https://vidtube.one/",
        "Origin": "https://vidtube.one",
    },
    "vidsrc": {
        "Referer": "https://vidsrc.me/",
        "Origin": "https://vidsrc.me",
    },
    "upbam": {
        "Referer": "https://upbam.org/",
        "Origin": "https://upbam.org",
    },
    "cdn-tube": {
        "Referer": "https://vidtube.one/",
        "Origin": "https://vidtube.one",
    },
    "dailymotion": {
        "Referer": "https://www.dailymotion.com/",
        "Origin": "https://www.dailymotion.com/",
    },
    "vk": {
        "Referer": "https://vk.com/",
        "Origin": "https://vk.com/",
    },
    "vkvideo": {
        "Referer": "https://vkvideo.ru/",
        "Origin": "https://vkvideo.ru/",
    },
    "voe": {
        "Referer": "https://voe.sx/",
        "Origin": "https://voe.sx/",
    },
    "archive": {
        "Referer": "https://archive.org/",
        "Origin": "https://archive.org/",
    },
    "myvidplay": {
        "Referer": "https://myvidplay.com/",
        "Origin": "https://myvidplay.com/",
    },
    "lulustream": {
        "Referer": "https://topcinemaa.com/",  # الخداع بأننا جايين من موقع الأفلام
        "Origin": "https://topcinemaa.com",
    },
    "luluvdo": {
        "Referer": "https://topcinemaa.com/",
        "Origin": "https://topcinemaa.com",
    },
    "mixdrop": {
        "Referer": "https://mixdrop.top/",
        "Origin": "https://mixdrop.top/",
    },
    "streamtape": {
        "Referer": "https://streamtape.com/",
        "Origin": "https://streamtape.com/",
    },
    "telegram_direct": {
        "Referer": "https://eslam315-egy-streamer.hf.space/",
        "Origin": "https://eslam315-egy-streamer.hf.space/",
    },
    "huggingface": {
        "Referer": "https://huggingface.co/",
        "Origin": "https://huggingface.co/",
    },
    "ok": {
        "Referer": "https://ok.ru",
        "Origin": "https://ok.ru",
    },
    "telecima": {
        "Referer": "https://telecima.sbs/",
        "Origin": "https://telecima.sbs/",
    },
    "cimafree": {
        "Referer": "https://cimafree.onl/",
        "Origin": "https://cimafree.onl/",
    },
    "topcinemaa": {
        "Referer": "https://topcinemaa.com/",
        "Origin": "https://topcinemaa.com/",
    },
    "geo.dailymotion": {
        "Referer": "https://geo.dailymotion.com/",
        "Origin": "https://geo.dailymotion.com/",
    },
    "goodstream": {
        "Referer": "https://goodstream.one/",
        "Origin": "https://goodstream.one",
    },
}

def get_smart_headers(url):
    """توليد هيدرز ذكية بناءً على رابط الموقع لكسر الحماية"""
    headers = []
    found = False
    try:
        for site, config in SITES_COOKBOOK.items():
            if site in url:
                for key, value in config.items():
                    headers.extend(["--add-header", f"{key}: {value}"])
                found = True
                break

        if not found:
            headers.extend(["--add-header", f"Referer: {url}"])
            headers.extend(["--add-header", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"])
            
    except Exception as e:
        log.error(f"⚠️ خطأ في توليد الهيدرز لـ {url}: {e}")
        
    return headers
