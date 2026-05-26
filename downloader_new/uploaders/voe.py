# /media/es/DDrive/projects/apps-python/egyPyramid-guardian-ultra/downloader_new/uploaders/voe.py
import os
import time
import httpx
import asyncio
from downloader_new.shared.logger import get_beast_logger
from functools import partial

log = get_beast_logger("GuardianUltra")
VOE_API_KEY = os.getenv("VOE_API_KEY")
# 1. استيراد القاعدة الأساسية أولاً
try:
    from tqdm.auto import tqdm as tqdm_base
except ImportError:
    import tqdm as tqdm_base
# 2. التعريف المعدل لبيئة السيرفرات (Hugging Face)
tqdm_custom = partial(
    tqdm_base,
    dynamic_ncols=False,
    mininterval=10.0,
    ascii=True,  # ✅ هذا يكفي لجعل اللوجات نصوص بسيطة
)
# 3. توحيد الاسم عالمياً لخدمة أي مكتبات خارجية ولإصلاح أخطاء Ruff
tqdm = tqdm_custom


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

            # 1. طلب الرفع مع محاولات إعادة في حال تذبذب الرابط
            res = {}
            for attempt in range(3):
                try:
                    response = await client.get(
                        "https://voe.sx/api/upload/url", params=params, timeout=30
                    )
                    res = response.json()
                    if res.get("status") == 200:
                        break
                except Exception as e:
                    log.warning(f"⚠️ Voe: فشل اتصال في المحاولة {attempt+1}: {e}")

                await asyncio.sleep(5)

            if res.get("status") != 200:
                log.error(f"❌ Voe: فشل الرفع نهائياً: {res}")
                return None

            file_code = res.get("result", {}).get("file_code")

            log.info(f"⏳ جاري متابعة حالة الرفع على Voe...")
            start_time = time.time()

            # تعريف شريط واحد فقط بتنسيق كامل ونظيف
            # ... قبل الحلقة ...
            check_count = 0
            pbar_voe = tqdm_custom(total=100, desc="⏳ Voe Polling")

            while time.time() - start_time < 800:
                try:
                    status_response = await client.get(
                        f"https://voe.sx/api/file/status?key={VOE_API_KEY}&file_code={file_code}"
                    )
                    status_res = status_response.json()
                    status = status_res.get("result", {}).get("status")

                    check_count += 1

                    if status == "finished":
                        pbar_voe.update(100 - pbar_voe.n)
                        pbar_voe.set_description("✅ Voe: Finished!")
                        pbar_voe.close()
                        return file_code

                    # المحاكاة الذكية: لو بيحمل حرك الشريط لغاية 40% ولو بيعالج حركه لغاية 80%
                    # المحاكاة الذكية: تعيين القيمة مباشرة بدلاً من update التراكمي في بعض الأحيان
                    if status == "downloading":
                        pbar_voe.n = min(40, pbar_voe.n + 5)
                    elif status == "processing":
                        pbar_voe.n = min(80, pbar_voe.n + 5)

                    pbar_voe.refresh()  # مهم جداً لرؤية الحركة فوراً

                    pbar_voe.set_description(
                        f"⏳ Voe Status: {status if status else 'Queued'}"
                    )
                    pbar_voe.refresh()

                    # صمام الأمان: لو السيرفر استهبل أكتر من دقيقتين والملف اترفع فعلاً
                    if check_count >= 5:
                        pbar_voe.set_description(
                            "⚠️ Voe Slow Response - Proceeding to VK..."
                        )
                        pbar_voe.close()
                        return file_code

                except:
                    pass

                await asyncio.sleep(25)

            pbar_voe.close()
            return file_code
    except Exception as e:
        log.error(f"⚠️ خطأ Voe API: {e}")
        return None
