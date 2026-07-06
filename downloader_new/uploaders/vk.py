# /media/es/DDrive/projects/apps-python/egyPyramid-guardian-ultra/downloader_new/uploaders/vk.py
import os
import time
import requests
from downloader_new.shared.logger import get_beast_logger

log = get_beast_logger("GuardianUltra")
VK_ACCESS_TOKEN = os.getenv("VK_ACCESS_TOKEN")
VK_GROUP_ID = os.getenv("VK_GROUP_ID")
VK_ALBUM_ID = os.getenv("VK_ALBUM_ID", "2")  # "2" كقيمة افتراضية إذا لم يوجد سكرت


def upload_to_vk_local(title, file_path):
    try:
        if not os.path.exists(file_path):
            log.error(f"⚠️ ملف VK غير موجود: {file_path}")
            return None

        # 1. حجز المكان
        api_url = "https://api.vk.com/method/video.save"
        params = {
            "name": title,
            "group_id": VK_GROUP_ID,
            "access_token": VK_ACCESS_TOKEN,
            "v": "5.131",
        }
        res_save = requests.get(api_url, params=params).json()

        if "response" not in res_save:
            error_info = res_save.get("error", {})
            err_code = error_info.get("error_code")
            err_msg = error_info.get("error_msg", "")

            if err_code == 7 or "has not right" in err_msg:
                log.error(
                    f"🚨 [VK CRITICAL] كود 7: تم رفض الصلاحية! الجروب ID: {VK_GROUP_ID} قد يكون محذوفاً، محظوراً، أو التوكن تالف."
                )
            else:
                log.error(f"❌ فشل حجز مكان في VK (كود {err_code}): {err_msg}")

            log.error(f"🔍 تفاصيل استجابة VK بالكامل: {res_save}")
            return None

        upload_url = res_save["response"]["upload_url"]
        video_id = res_save["response"]["video_id"]
        owner_id = res_save["response"]["owner_id"]

        # --- [ مرحلة الضخ السريع ] ---
        log.info(f"📡 جاري ضخ الفيديو لـ VK بنظام Stream (المسار المحلي)...")
        try:
            with open(file_path, "rb") as f:
                files = {"video_file": (os.path.basename(file_path), f, "video/mp4")}
                response = requests.post(upload_url, files=files, timeout=600)

            if response.status_code != 200:

                log.error(f"❌ فشل ضخ الملف لـ VK: Status {response.status_code}")
                log.error(f"🔍 تفاصيل الرفض من السيرفر: {response.text}")
                return None
            log.info("   ✅ انتهى الضخ بنجاح. يبدأ الآن فحص المعالجة وقنص الرابط...")
        except Exception as e:
            log.error(f"   ❌ خطأ أثناء الضخ المحلي: {str(e)}")
            return None

        # --- [ مرحلة القنص الذكي - Polling ] ---
        for check_attempt in range(1, 31):
            time.sleep(30)
            get_url = "https://api.vk.com/method/video.get"
            get_params = {
                "videos": f"{owner_id}_{video_id}",
                "access_token": VK_ACCESS_TOKEN,
                "v": "5.131",
            }
            try:
                res_get = requests.get(get_url, params=get_params).json()
                if "response" in res_get and res_get["response"].get("items"):
                    video_data = res_get["response"]["items"][0]
                    embed_url = video_data.get("player")
                    if embed_url:
                        final_url = embed_url.replace("vk.com", "vkvideo.ru")
                        connector = "&" if "?" in final_url else "?"
                        final_url += f"{connector}hd=2&autoplay=0"
                        log.info(f"✅ تم القنص بنجاح لـ VK! | الرابط: {final_url}")
                        return final_url
                log.info(f"⏳ VK يعالج الفيديو حالياً ({check_attempt}/30)...")
            except Exception as e:
                log.warning(f"⚠️ خطأ في فحص المعالجة: {e}")

        # --- [ الحل الاحتياطي الأخير لو الفحص فشل بعد 15 دقيقة ] ---
        access_key = res_save["response"].get("access_key", "")
        fallback_url = f"https://vkvideo.ru/video_ext.php?oid={owner_id}&id={video_id}&hash={access_key}&hd=2"
        log.warning(
            f"⚠️ فشل استخراج Embed تلقائياً، تم بناء رابط احتياطي: {fallback_url}"
        )
        return fallback_url

    except Exception as e:
        import traceback

        log.error(f"⚠️ فشل VK المحلي: {e}")
        log.error(f"🔍 تفاصيل الخطأ البرمجي:\n{traceback.format_exc()}")
        return None
