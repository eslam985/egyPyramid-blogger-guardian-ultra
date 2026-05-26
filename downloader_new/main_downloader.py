# /media/es/DDrive/projects/apps-python/egyPyramid-guardian-ultra/downloader_new/main_downloader.py
import os
from downloader_new.shared.logger import get_beast_logger
from downloader_new.core.orchestrator import pyramid_ultimate_beast
# إعدادات النظام - توضع هنا لضمان تطبيقها على كل الاستيرادات التالية
os.environ["PYROGRAM_MAX_CONCURRENT_TRANSMISSIONS"] = "1"
os.environ["PYROGRAM_SLEEP_THRESHOLD"] = "300"
os.environ["TQDM_MININTERVAL"] = "2.0"


import nest_asyncio
from dotenv import load_dotenv

# تحميل متغيرات البيئة لو شغال لوكل
load_dotenv()

# تفعيل nest_asyncio لدعم asyncio في بيئات مثل Jupyter أو HuggingFace
nest_asyncio.apply()
log = get_beast_logger("GuardianUltra")


async def run_pyramid_tasks(task_list):
    if not task_list:
        log.warning("⚠️ تنبيه: قائمة المهام فارغة!")
        return

    for i, task in enumerate(task_list, 1):
        url = task.get("url")
        name = task.get("name")
        episode_id = task.get("episode_id")  # 👈 جلب الـ ID من المهمة

        if not url:
            continue

        log.info(f"\n🎬 معالجة ({i}/{len(task_list)}): {name}")
        try:
            # تمرير الـ episode_id للوحش عشان يوصل لـ Supabase
            await pyramid_ultimate_beast(url, name, task_id=episode_id)
        except Exception as e:
            log.error(f"❌ خطأ في '{name}': {e}")


# التعديل المطلوب لضمان الاستقلالية التامة
async def start_download_process(url, name):
    """المدخل الرئيسي - يدعم كاجل، كولاب، والجهاز المحلي"""
    log.info(f"\n🚀 انطلاق الوحش لمعالجة: {name}")
    try:
        # 1. فحص البيئة وتحديد المسار الآمن للكتابة
        if os.path.exists("/kaggle/working"):
            target_path = "/kaggle/working"
        elif os.path.exists("/content"):  # مسار كولاب الافتراضي
            target_path = "/content"
        else:
            target_path = os.getcwd()  # لو شغال على جهازك الشخصي

        # 2. طباعة البيئة المكتشفة فقط بدون تغيير المسار هنا
        log.info(f"📂 البيئة المكتشفة: {target_path}")

        # 3. انطلاق المحرك (المحرك هو المسؤول عن تنظيم مجلداته)
        await pyramid_ultimate_beast(url, name)

    except Exception as e:
        log.error(f"❌ خطأ كارثي في معالجة '{name}': {e}")
