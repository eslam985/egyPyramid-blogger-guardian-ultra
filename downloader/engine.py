import os
import re
import shutil
import subprocess
import requests
import time
import asyncio
from pyrogram import Client
from internetarchive import upload as archive_upload
from supabase import create_client, Client as SupabaseClient
from functools import partial  # استيراد واحد يكفي

try:
    from tqdm import tqdm as tqdm_base
except ImportError:
    import tqdm as tqdm_base

# التعريف الموحد (الوحش الآن جاهز)
tqdm_custom = partial(
    tqdm_base, dynamic_ncols=False, mininterval=2.0, ascii=" #", ncols=80
)

# توحيد الاسم لمنع انهيار المكتبات الخارجية مثل VK
tqdm = tqdm_custom

# إعدادات سوبابيز
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: SupabaseClient = create_client(SUPABASE_URL, SUPABASE_KEY)

ARCHIVE_ACCESS_KEY = os.getenv("ARCHIVE_ACCESS_KEY")
ARCHIVE_SECRET_KEY = os.getenv("ARCHIVE_SECRET_KEY")

# ضعه في منطقة الـ Variables في الأعلى
# جلب القيم كمناص نصية أولاً
TELE_ID_RAW = os.getenv("TELEGRAM_API_ID")
TELE_HASH_RAW = os.getenv("TELEGRAM_API_HASH")

# سيتم التحويل والتحقق داخل دالة الرفع لضمان عدم توقف السكريبت بالكامل
BOT_TOKEN = os.getenv("BOT_TOKEN")

# جلب الوجهات وتجنب خطأ القائمة الفارغة
dest_raw = os.getenv("DESTINATIONS") or os.getenv("TELEGRAM_CHAT_ID") or ""
DESTINATIONS = [d.strip() for d in dest_raw.split(",") if d.strip()]


class PyrogramProgress:
    def __init__(self, name, dest_count, current_dest, episode_id=None):
        self.pbar = None
        self.name = name
        self.episode_id = episode_id
        self.dest_info = f"({current_dest}/{dest_count})"
        self.last_update_time = 0

    def update(self, current, total):
        if not self.pbar:
            self.pbar = tqdm_custom(
                total=total,
                desc=f"📤 {self.dest_info} {self.name}",
                unit="B",
                unit_scale=True,
                mininterval=2.0,  # التعديل هنا: تحديث كل ثانيتين
            )

        self.pbar.update(current - self.pbar.n)

        # الحقيقة الصارمة: تحديث واحد فقط كل ثانيتين يكفي جداً
        now = time.time()
        if self.episode_id and (now - self.last_update_time > 2):
            percent = int((current / total) * 100)
            try:
                supabase.table("episodes").update(
                    {
                        "status_message": f"📤 رفع تليجرام {self.dest_info}",
                        "progress_percent": percent,
                        "download_speed": "Telegram",
                    }
                ).eq("id", self.episode_id).execute()
                self.last_update_time = now
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

            # تحديث كل ثانيتين لضمان استقرار الاتصال وسلاسة الواجهة
            if self.episode_id and (time.time() - self.last_update_time > 2):
                # حماية من القسمة على صفر إذا لم يكتمل تحميل الـ pbar
                total = self.pbar.total if self.pbar.total else 1
                percent = int((self.pbar.n / total) * 100)
                try:
                    supabase.table("episodes").update(
                        {
                            "status_message": "☁️ جاري الرفع للأرشيف...",
                            "progress_percent": percent,
                            "download_speed": "Uploading...",
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
    print(f"📤 رفع واستخراج رابط تليجرام المباشر: {display_name}")

    # التحقق الذكي من وجود المفاتيح وصحتها
    if not TELE_ID_RAW or not TELE_HASH_RAW:
        print("❌ خطأ: مفاتيح Telegram (API_ID/HASH) غير موجودة في الـ Secrets.")
        return None

    try:
        final_api_id = int(TELE_ID_RAW)
        final_api_hash = TELE_HASH_RAW
    except ValueError:
        print("❌ خطأ: TELEGRAM_API_ID يجب أن يكون رقماً فقط.")
        return None

    async with Client(
        "egy_pyramid_user",
        api_id=final_api_id,
        api_hash=final_api_hash,
        in_memory=False,
    ) as app:

        # 1. الرفع للمخزن (أول وجهة في القائمة)
        dest = DESTINATIONS[0].strip()
        tracker = PyrogramProgress(display_name, 1, 1, episode_id)

        try:
            sent_video = await app.send_video(
                chat_id=int(dest),
                video=file_path,
                supports_streaming=True,
                caption=f"🎬 **{display_name}**\n✅ بواسطة **Egy Pyramid**",
                progress=lambda c, t: tracker.update(c, t),
            )

            if sent_video:
                print(f"🔄 جاري عمل Forward للبوت لاستخراج الرابط...")
                # 2. عمل Forward لبوت الاستخراج
                await sent_video.forward("@EgyPyramid_stream_bot")

                # 3. انتظار الرد (تكتيك الصياد)
                await asyncio.sleep(5)  # وقت كافٍ للبوت ليرد

                async for message in app.get_chat_history(
                    "@EgyPyramid_stream_bot", limit=1
                ):
                    if message.text and "http" in message.text:
                        # استخراج الرابط باستخدام regex بسيط

                        links = re.findall(r"(https?://[^\s]+)", message.text)
                        # --- التعديل ليتوافق مع جدول links ---
                        if links:
                            direct_link = links[0]
                            print(f"✅ تم صيد الرابط المباشر: {direct_link}")

                            if episode_id:
                                # استخدام كائن supabase المعرف في أعلى الملف مباشرة
                                supabase.table("links").upsert(
                                    {
                                        "episode_id": episode_id,
                                        "server_name": "telegram_direct",
                                        "url": direct_link,
                                    },
                                    on_conflict="episode_id, server_name",
                                ).execute()
                                print(
                                    f"🔗 تم ربط رابط التليجرام بالحلقة {episode_id} في جدول links"
                                )

        except Exception as e:
            print(f"❌ فشل في عملية التليجرام: {e}")
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
