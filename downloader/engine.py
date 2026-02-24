import os
import shutil
import subprocess
from pyrogram import Client
from internetarchive import upload as archive_upload
from tqdm import tqdm  # سنغيرها لاحقاً لـ tqdm العادية بدلاً من notebook
import requests

# أضف هذه الأسطر تحت import requests
from supabase import create_client, Client as SupabaseClient

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: SupabaseClient = create_client(SUPABASE_URL, SUPABASE_KEY)

API_ID = os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("TELEGRAM_API_HASH")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ARCHIVE_ACCESS_KEY = os.getenv("ARCHIVE_ACCESS_KEY")
ARCHIVE_SECRET_KEY = os.getenv("ARCHIVE_SECRET_KEY")
# تحويل السلسلة النصية القادمة من السكرت إلى قائمة (List)
DESTINATIONS = os.getenv("TELEGRAM_CHAT_ID", "").split(",")


class PyrogramProgress:
    def __init__(self, name, dest_count, current_dest, episode_id=None):
        self.pbar = None
        self.name = name
        self.episode_id = episode_id
        self.dest_info = f"({current_dest}/{dest_count})"
        self.last_update_time = 0

    def update(self, current, total):
        if not self.pbar:
            self.pbar = tqdm(
                total=total,
                desc=f"📤 {self.dest_info} {self.name}",
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
            )
        self.pbar.update(current - self.pbar.n)

        # تحديث ساب باز كل ثانيتين لتقليل الضغط على الـ API
        import time

        if self.episode_id and (time.time() - self.last_update_time > 2):
            percent = int((current / total) * 100)
            try:
                supabase.table("episodes").update(
                    {
                        "status_message": f"Uploading to Telegram {self.dest_info}",
                        "progress_percent": percent,
                        "download_speed": "Telegram Upload",
                    }
                ).eq("id", self.episode_id).execute()
                self.last_update_time = time.time()
            except:
                pass


async def ensure_dependencies():
    print("🔍 جاري فحص الأدوات الأساسية...")
    if not shutil.which("yt-dlp"):
        subprocess.run(
            "curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o /usr/local/bin/yt-dlp && chmod a+rx /usr/local/bin/yt-dlp",
            shell=True,
        )

    # إضافة فحص unrar و ffprobe
    if not shutil.which("unrar") or not shutil.which("ffprobe"):
        print("📥 unrar أو ffprobe مفقود، جاري التثبيت...")
        subprocess.run("apt-get update && apt-get install -y unrar ffmpeg", shell=True)

    print("✅ جميع الأدوات جاهزة للعمل.")


class ProgressStream:
    def __init__(self, filename, pbar, episode_id=None):
        self.fd = open(filename, "rb")
        self.pbar = pbar
        self.episode_id = episode_id
        self.last_update_time = 0

    def read(self, size=-1):
        chunk = self.fd.read(size)
        if chunk:
            self.pbar.update(len(chunk))
            # تحديث ساب باز أثناء رفع الأرشيف
            import time

            if self.episode_id and (time.time() - self.last_update_time > 2):
                percent = int((self.pbar.n / self.pbar.total) * 100)
                try:
                    supabase.table("episodes").update(
                        {
                            "status_message": "Uploading to Archive...",
                            "progress_percent": percent,
                        }
                    ).eq("id", self.episode_id).execute()
                    self.last_update_time = time.time()
                except:
                    pass
        return chunk

    # ... باقي الدوال (tell, seek, etc.) تبقى كما هي ...

    # هما السطران اللذان كانا ينقصان الكود:
    def tell(self):
        return self.fd.tell()

    def seek(self, offset, whence=0):
        return self.fd.seek(offset, whence)

    def __len__(self):

        return os.path.getsize(self.fd.name)

    def close(self):
        self.fd.close()


# --- الدالة الجديدة التي ستحل محل upload_file_to_all ---
# تعديل رأس الدالة لإضافة episode_id
async def upload_to_telegram_only(file_path, display_name, episode_id=None):
    print(f"📤 رفع لتليجرام: {display_name}")
    async with Client(
        "egy", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN
    ) as app:
        for i, dest in enumerate(DESTINATIONS, 1):
            # تمرير episode_id للـ tracker
            tracker = PyrogramProgress(display_name, len(DESTINATIONS), i, episode_id)
            try:
                await app.send_video(
                    chat_id=int(dest.strip()),  # هنا تم إضافة strip()
                    video=file_path,
                    supports_streaming=True,
                    caption=f"🎬 **{display_name}**\n✅ بواسطة **Egy Pyramid**",
                    progress=lambda c, t: tracker.update(c, t),
                )
            except Exception as e:
                print(f"❌ فشل تليجرام {dest}: {e}")
            finally:
                if tracker.pbar:
                    tracker.pbar.close()


# 1. الدالة الجديدة المضافة (البحث في توب سينما كخطة بديلة)
def get_topcinema_data(name):
    try:
        # ملاحظة: توب سينما غالباً ما يحتاج سكريبت متطور لتخطي الحماية
        # سنحاول سحبه بالهيدرز الأساسية
        search_url = f"https://topcinema.rip/?s={name.replace(' ', '+')}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        res = requests.get(search_url, headers=headers, timeout=10)
        # إذا نجح السحب سنقوم بمعالجة النص هنا (هذه الدالة للبحث فقط حالياً)
        return None
    except:
        return None
