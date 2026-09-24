# /media/es/DDrive/projects/apps-python/egyPyramid-guardian-ultra/downloader_new/uploaders/voe.py
import os
import time
import httpx
import asyncio
from downloader_new.shared.logger import get_beast_logger

log = get_beast_logger("Veo_Loger")
VOE_API_KEY = os.getenv("VOE_API_KEY")

async def upload_to_voe_api(file_path, identifier):
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:  # أضف هذا السطر هنا

            file_name = os.path.basename(file_path).replace(" ", "%20")
            # إذا كان الرابط جاهز نستخدمه، وإلا نبنيه من أرشيف
            remote_url = (
                identifier
                if str(identifier).startswith("http")
                else f"https://archive.org/download/{identifier}/{file_name}"
            )
            params = {"key": VOE_API_KEY, "url": remote_url}

            # 1. طلب الرفع مع معالجة الـ Rate Limit
            res = {}
            for attempt in range(5):  # زيادة المحاولات لتفادي الـ Rate Limit
                try:
                    response = await client.get(
                        "https://voe.sx/api/upload/url", params=params, timeout=30
                    )
                    
                    # فحص الـ Rate Limit
                    if response.status_code == 429:
                        wait_time = 15 * (attempt + 1)
                        log.warning(f"⚠️ Voe [Rate Limit]: تم حظر الطلب مؤقتاً (429). الانتظار {wait_time} ثانية... (المحاولة {attempt+1})")
                        await asyncio.sleep(wait_time)
                        continue

                    res = response.json()
                    if res.get("status") == 200:
                        log.info("✅ Voe: تم قبول طلب الرفع بنجاح.")
                        break
                    else:
                        log.warning(f"⚠️ Voe: فشل الطلب بالرد: {res}")
                except Exception as e:
                    log.warning(f"⚠️ Voe: فشل اتصال في المحاولة {attempt+1}: {e}")

                await asyncio.sleep(5)

            if res.get("status") != 200:
                log.error(f"❌ Voe: فشل الرفع نهائياً: {res}")
                return None

            file_code = res.get("result", {}).get("file_code")
            
            log.info(f"⏳ Voe: جاري متابعة حالة الرفع للملف ({file_code})...")
            start_time = time.time()

            check_count = 0
            last_status = None

            while time.time() - start_time < 800:
                try:
                    status_response = await client.get(
                        f"https://voe.sx/api/file/status?key={VOE_API_KEY}&file_code={file_code}",
                        timeout=15
                    )
                    
                    if status_response.status_code == 429:
                        log.warning("⚠️ Voe [Rate Limit]: جاري تخفيف الضغط أثناء فحص الحالة...")
                        await asyncio.sleep(25)
                        continue

                    status_res = status_response.json()
                    status = status_res.get("result", {}).get("status", "unknown")

                    # تسجيل الحالة فقط إذا تغيرت لمنع الـ Spam في اللوج
                    if status != last_status:
                        log.info(f"🔄 Voe Status: الحالة الآن [{status}]")
                        last_status = status

                    check_count += 1

                    if status == "finished":
                        log.info("✅ Voe: تم الرفع والمعالجة بنجاح!")
                        return file_code

                    # صمام الأمان: لو السيرفر تأخر أكثر من اللازم (5 فحوصات = 125 ثانية تقريباً)
                    if check_count >= 5:
                        log.info("⚠️ Voe: تأخر رد السيرفر النهائي، سيتم المتابعة وتجاوز الانتظار...")
                        return file_code

                except Exception as e:
                    # نستخدم debug هنا لتجنب تشويه اللوج إذا حدثت مشكلة شبكة عابرة
                    log.debug(f"⚠️ Voe: خطأ أثناء فحص الحالة (سيتم التجاهل والمحاولة لاحقاً): {e}")

                await asyncio.sleep(25)

            log.warning("❌ Voe: انتهى وقت الانتظار (Timeout) المخصص للمعالجة.")
            return file_code
    except Exception as e:
        log.error(f"⚠️ خطأ Voe API: {e}")
        return None
