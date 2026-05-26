

# /media/es/DDrive/projects/apps-python/egyPyramid-guardian-ultra/downloader_new/metadata/images.py
import requests
import os
from downloader_new.shared.logger import get_beast_logger
log = get_beast_logger("GuardianUltra")

def upload_poster_to_cloudinary(image_url):
    """رفع البوستر ومعالجته لكلاود ناري بترميز WebP المتوافق مع تليجرام وبلوجر"""
    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME")
    upload_preset = os.getenv("CLOUDINARY_UPLOAD_PRESET")

    if not cloud_name or not upload_preset:
        return image_url
    log.info("📸 جاري رفع الصورة لكلاود ناري...")
    try:
        cloudinary_api = f"https://api.cloudinary.com/v1_1/{cloud_name}/image/upload"
        payload = {
            "file": image_url,
            "upload_preset": upload_preset,
            "folder": "blogger",
        }
        res = requests.post(cloudinary_api, data=payload).json()
        public_id = res.get("public_id")

        if public_id:
            # f_webp: تجعل كلاود ناري يسلم الصورة بصيغة WebP مهما كان الأصل
            # q_auto:good: تعطي جودة ممتازة مع حجم صغير جداً
            transform = "c_fill,g_auto,w_300,h_450,q_auto:good,f_avif"

            return f"https://res.cloudinary.com/{cloud_name}/image/upload/{transform}/v1/{public_id}.avif"

        return image_url
    except Exception as e:
        log.warning(f"⚠️ خطأ في رفع الصورة لكلاود ناري: {e}")
        return image_url