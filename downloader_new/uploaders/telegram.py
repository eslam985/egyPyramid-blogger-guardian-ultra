# /media/es/DDrive/projects/apps-python/egyPyramid-guardian-ultra/downloader_new/uploaders/telegram.py
import os
import asyncio
import time
import re
import json
import requests
from datetime import datetime
from pyrogram import Client
from pyrogram.errors import FloodWait

# استيراد كائن supabase الجاهز من مجلد db
from downloader_new.db.supabase_client import supabase
from downloader_new.shared.templates import generate_facebook_template
from downloader_new.shared.logger import get_beast_logger

log = get_beast_logger("GuardianUltra")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_DESTINATION") or os.getenv("DESTINATIONS")
dest_raw = os.getenv("DESTINATIONS") or os.getenv("TELEGRAM_CHAT_ID") or ""
DESTINATIONS = [d.strip() for d in dest_raw.split(",") if d.strip()]


class PyrogramProgress:
    def __init__(self, name, dest_count, current_dest, episode_id=None):
        self.name = name
        self.episode_id = episode_id
        self.started = False

    def update(self, current, total):
        # سنكتفي بطباعة رسالة البدء فقط في الـ Console لمرة واحدة
        if not self.started:
            print(f"🚀 [Telegram] بدأت عملية الرفع للملف: {self.name}...")
            self.started = True

    def close(self):
        print(f"✅ [Telegram] انتهت محاولة الرفع.")


class ProgressStream:
    def __init__(self, filename, pbar, episode_id=None):
        self.fd = open(filename, "rb")
        self.episode_id = episode_id
        self.filename = os.path.basename(filename)
        print(
            f"☁️ جاري سحب {self.filename} للأرشيف (بدون شريط تقدم لضمان الاستقرار)..."
        )

    def read(self, size=-1):
        # قراءة خام مباشرة - أسرع وأخف حاجة ممكنة
        return self.fd.read(size)

    def tell(self):
        return self.fd.tell()

    def seek(self, offset, whence=0):
        return self.fd.seek(offset, whence)

    def __len__(self):
        return os.path.getsize(self.fd.name)

    def close(self):
        self.fd.close()


async def upload_to_telegram_only(file_path, display_name, episode_id=None):
    log.info(f"📤 رفع واستخراج رابط تليجرام المباشر: {display_name}")
    # 1. جلب القيم من بيئة النظام
    t_id = os.environ.get("TELEGRAM_API_ID") or os.environ.get("API_ID")
    t_hash = os.environ.get("TELEGRAM_API_HASH") or os.environ.get("API_HASH")
    tele_string = os.environ.get("TELEGRAM_STRING_SESSION")

    # 2. خيار احتياطي من Colab userdata
    if not t_id or not t_hash or not tele_string:
        try:
            from google.colab import userdata

            t_id = t_id or userdata.get("TELEGRAM_API_ID")
            t_hash = t_hash or userdata.get("TELEGRAM_API_HASH")
            tele_string = tele_string or userdata.get("TELEGRAM_STRING_SESSION")
        except Exception as e:
            log.error(f"❌ خطأ في جلب مفاتيح Telegram: {e}")
            pass

    # 3. التحقق النهائي وتحويل النوع
    try:
        f_api_id = int(t_id) if t_id else None
        f_api_hash = t_hash
    except Exception as e:
        log.error(f"❌ خطأ في معالجة أرقام الـ ID: {e}")
        return None

    if not f_api_id or not f_api_hash or not tele_string:
        log.error("❌ خطأ: بيانات Telegram غير مكتملة.")
        return None

    dest = DESTINATIONS[0].strip()
    tracker = PyrogramProgress(display_name, 1, 1, episode_id)
    sent_video = None

    # حلقة الرفع
    while True:
        try:
            async with Client(
                name=f"bot_{int(time.time())}",
                session_string=tele_string,
                api_id=f_api_id,
                api_hash=f_api_hash,
                workers=1,
                sleep_threshold=300,
            ) as app:
                await asyncio.sleep(2)
                log.info(f"🚀 [Telegram] بدأ الرفع الصامت للملف...")
                # البحث عن سطر الرفع القديم واستبداله بهذا لتعطيل الـ Callback تماماً
                sent_video = await app.send_video(
                    chat_id=int(dest),
                    video=file_path,
                    supports_streaming=True,
                    caption=f"🎬 **{display_name}**\n✅ بواسطة **Egy Pyramid**",
                    progress=None,  # تعطيل التحديثات لمنع الـ Flood
                )
                if sent_video:
                    break
        except FloodWait as e:
            log.warning(f"⚠️ Telegram FloodWait: انتظار {e.value + 5} ثانية...")
            await asyncio.sleep(e.value + 5)
            continue
        except Exception as e:
            log.error(f"❌ خطأ أثناء الرفع: {e}")
            await asyncio.sleep(10)
            continue

    tracker.close()

    # استخراج الرابط
    async with Client(
        name=f"bot_fetch_{int(time.time())}",
        session_string=tele_string,
        api_id=f_api_id,
        api_hash=f_api_hash,
        sleep_threshold=60,
    ) as app:
        if sent_video:
            log.info(f"🔄 جاري عمل Forward للبوت لاستخراج الرابط...")
            await sent_video.forward("@EgyPyramid_stream_bot")
            await asyncio.sleep(8)

            async for message in app.get_chat_history(
                "@EgyPyramid_stream_bot", limit=1
            ):
                if message.text and "http" in message.text:
                    links = re.findall(r"(https?://[^\s]+)", message.text)
                    if links:
                        direct_link = links[0]
                        print(f"✅ تم صيد الرابط المباشر: {direct_link}")

                        if episode_id:
                            supabase.table("links").upsert(
                                {
                                    "episode_id": episode_id,
                                    "server_name": "telegram_direct",
                                    "url": direct_link,
                                },
                                on_conflict="episode_id, server_name",
                            ).execute()
                            print(f"🔗 تم ربط الرابط بالحلقة {episode_id}")
                            return direct_link

    # محاولة أخيرة لو فشل الاستخراج
    if episode_id:
        try:
            res = (
                supabase.table("links")
                .select("url")
                .eq("episode_id", episode_id)
                .eq("server_name", "telegram_direct")
                .execute()
            )
            if res.data:
                return res.data[0]["url"]
        except Exception as e:
            log.error(f"❌ خطأ أثناء التحقق من قاعدة البيانات: {e}")

    return "failed_but_continue"


def send_to_telegram(row, content_type, action_text, post_url, lang_val="لغة أصلية"):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ خطأ: مفاتيح تليجرام غير موجودة")
        return

    human_date = datetime.now().strftime("%Y-%m-%d")
    facebook_post = generate_facebook_template(
        row, human_date, content_type, action_text, lang_val
    )

    # محاولة جلب الرابط من كافة المفاتيح المحتملة
    photo_url = row.get("poster_url") or row.get("poster") or row.get("image")

    # تأمين النص (1024 للصورة، 4000 للنص العادي)
    limit = 1024 if photo_url else 4000
    safe_caption = (
        facebook_post
        if len(facebook_post) < limit
        else facebook_post[: limit - 50] + "..."
    )

    final_url = (
        post_url
        if str(post_url).startswith("http")
        else "https://egypyramid.vercel.app/"  # رابط احتياطي في حال كان post_url غير صالح
    )

    keyboard = {
        "inline_keyboard": [
            [{"text": "🍿 مشاهدة الآن (المقال الرسمي)", "url": final_url}]
        ]
    }

    # التبديل التلقائي بين إرسال صورة أو نص
    if photo_url and str(photo_url).startswith("http"):
        method = "sendPhoto"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "photo": photo_url,
            "caption": safe_caption,
            "reply_markup": json.dumps(keyboard),
        }
    else:
        print("⚠️ لم يتم العثور على بوستر، سيتم الإرسال كنص فقط.")
        method = "sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": safe_caption,
            "reply_markup": json.dumps(keyboard),
        }

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}"

    try:
        response = requests.post(url, json=payload, timeout=20)
        if response.status_code == 200:
            print(f"✈️ تم إرسال التحديث إلى تليجرام بنجاح!")
            return True
        else:
            print(f"⚠️ تليجرام رفض ({method}): {response.text}")
            return False
    except Exception as e:
        print(f"⚠️ فشل إرسال التحديث: {e}")
        return False


# اجعل المتغير يشير للدالة الحقيقية مباشرة
send_telegram_update = send_to_telegram
