# /media/es/DDrive/projects/apps-python/egyPyramid-guardian-ultra/downloader_new/core/workspace.py
import os
import httpx
import shutil
import subprocess
from downloader_new.shared.logger import get_beast_logger

log = get_beast_logger("GuardianUltra")


def setup_workspace() -> dict:
    """
    تجهيز بيئة العمل: تحديد المسارات، إنشاء المجلدات، تحميل اللوجو، تغيير الدليل.
    تعيد قاموساً يحتوي على BASE_PATH, BASE_DIR, TOOLS_DIR, LOGO_FILE.
    """
    # تحديد مسار العمل الأساسي
    if os.path.exists("/content"):
        BASE_PATH = "/content"
    elif os.path.exists("/kaggle/working"):
        BASE_PATH = "/kaggle/working"
    else:
        BASE_PATH = os.getcwd()

    current_root = os.getcwd()
    if current_root.endswith("project"):
        BASE_DIR = current_root
    else:
        BASE_DIR = os.path.join(current_root, "project")

    os.makedirs(BASE_DIR, exist_ok=True)
    if os.getcwd() != BASE_DIR:
        os.chdir(BASE_DIR)

    TOOLS_DIR = os.path.join(BASE_PATH, "tools")
    os.makedirs(TOOLS_DIR, exist_ok=True)

    LOGO_URL = "https://res.cloudinary.com/dbahqgo8j/image/upload/q_auto,f_auto,w_80,h_80,c_fill,r_max/blogger/logo.webp"
    LOGO_FILE = os.path.join(TOOLS_DIR, "watermark.webp")

    if not os.path.exists(LOGO_FILE):
        try:
            with httpx.Client(follow_redirects=True) as client:
                resp = client.get(LOGO_URL)
                resp.raise_for_status()  # التأكد من نجاح الطلب
                with open(LOGO_FILE, "wb") as f:
                    f.write(resp.content)
            log.info("✅ اللوجو جاهز ومؤمن في مجلد الأدوات.")
        except Exception as e:
            log.warning(f"⚠️ فشل تحميل اللوجو: {e}. سيستمر البرنامج بدون علامة مائية.")

    log.info(f"🛠️ مسار العمل الحالي للوحش: {os.getcwd()}")

    return {
        "BASE_PATH": BASE_PATH,
        "BASE_DIR": BASE_DIR,
        "TOOLS_DIR": TOOLS_DIR,
        "LOGO_FILE": LOGO_FILE,
    }


async def ensure_dependencies():
    try:
        log.info("🔍 جاري فحص الأدوات الأساسية...")
        if not shutil.which("yt-dlp"):
            subprocess.run(
                "curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o /usr/local/bin/yt-dlp && chmod a+rx /usr/local/bin/yt-dlp",
                shell=True,
                check=True,
            )

        if not shutil.which("unrar") or not shutil.which("ffprobe"):
            log.info("📥 جاري تجهيز المستودعات وتثبيت unrar/ffmpeg...")
            cmd = "apt-get update && apt-get install -y unrar-free ffmpeg || apt-get install -y unrar ffmpeg"
            subprocess.run(cmd, shell=True, check=True)

        log.info("✅ جميع الأدوات جاهزة للعمل.")
    except Exception as e:
        log.error(f"❌ خطأ أثناء تثبيت الأدوات: {e}")
