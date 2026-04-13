import os
import re
import shutil
import subprocess
import requests
import time
import asyncio
import json

from pyrogram import Client
from internetarchive import upload as archive_upload
from supabase import create_client, Client as SupabaseClient
from functools import partial  # استيراد واحد يكفي
from datetime import datetime
from groq import Groq


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

# تعريف العميل باستخدام المفتاح الموجود في ملف .env
# هذا السطر هو الذي سيحل خطأ Undefined name "client_groq"
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# إنشاء العميل فقط إذا كان المفتاح موجوداً لتجنب انهيار الاستيراد
client_groq = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# التعديل ليتوافق مع أسماء المتغيرات في خلية الحقن
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_DESTINATION") or os.getenv("DESTINATIONS")

# استدعاء المفاتيح من ملف .env
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")


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

    # 1. جلب المفاتيح الخام وتحويل الـ API_ID لرقم
    try:
        f_api_id = int(TELE_ID_RAW) if TELE_ID_RAW else None
        f_api_hash = TELE_HASH_RAW
    except (ValueError, TypeError):
        print("❌ خطأ: TELEGRAM_API_ID يجب أن يكون رقماً صحيحاً.")
        return None

    if not f_api_id or not f_api_hash:
        print("❌ خطأ: مفاتيح Telegram (API_ID/HASH) مفقودة.")
        return None

    # 2. جلب كود الجلسة (String Session)
    tele_string = os.getenv("TELEGRAM_STRING_SESSION")

    if not tele_string:
        try:
            from google.colab import userdata

            tele_string = userdata.get("TELEGRAM_STRING_SESSION")
            # حجر الزاوية: حقن المتغير في النظام لضمان استمراره
            if tele_string:
                os.environ["TELEGRAM_STRING_SESSION"] = tele_string
        except Exception:
            pass

    if not tele_string:
        print("❌ خطأ قاتل: TELEGRAM_STRING_SESSION غير موجود في الـ Secrets!")
        return None

    # 3. الوحش يدخل الآن "In-Memory"
    async with Client(
        "egy_pyramid_session",
        session_string=tele_string,
        api_id=f_api_id,
        api_hash=f_api_hash,
        in_memory=True,
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
                                return direct_link  # هذا السطر هو الذي سينقذ السيرفرات الخمسة

        except Exception as e:
            print(f"❌ فشل في عملية التليجرام: {e}")
            return None
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
    except (ImportError, Exception):
        return None


def generate_facebook_template(row, human_date, content_type, action_text, lang_val):
    raw_title = row.get("title", "")
    # حذف الكلمات المتكررة لضمان عدم ظهورها بجانب الإيموجي
    clean_title = (
        raw_title.replace("مشاهدة مسلسل", "")
        .replace("مشاهدة فيلم", "")
        .replace("مسلسل", "")
        .replace("فيلم", "")
        .split("[")[0]
        .split("جميع")[0]
        .strip()
    )
    story = row.get("story", "")
    # التعديل الاختياري: لجعل القصة في المنشور تنتهي بكلمة كاملة أيضاً
    short_story = story[:160].rsplit(" ", 1)[0] + "..." if len(story) > 160 else story

    # --- الجزء الذكي: توليد "Hook" مشوق بواسطة الذكاء الاصطناعي ---
    hook_text = f"استمتع بمشاهدة {clean_title} بجودة عالية."  # نص احتياطي
    try:
        # تم الحفاظ على البرومت الأصلي مع إضافة شروط لغة صارمة في نهايته
        # --- برومبت متطور يعتمد على الصدمة في القصة ---
        prompt = f"""بناءً على قصة العمل التالية: ({short_story})
        اكتب جملة واحدة فقط (Hook) تكون صادمة أو مشوقة جداً تجذب القارئ.
        الشروط الصارمة:
        1. ممنوع نهائياً ذكر اسم العمل ({clean_title}) داخل الجملة.
        2. ابدأ مباشرة بالحدث المثير  من القصة.
        3. استخدم عامية مصرية بسيطة ومثيرة.
        4. إيموجي في نهاية الجملة معبره عن القصة.
        5. لا تزد عن 30 كلمة."""

        completion = client_groq.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,  # خفض الـ temperature لـ 0.6 يضمن دقة لغوية أعلى
            max_tokens=40,
        )

        hook_text = (
            completion.choices[0]
            .message.content.strip()
            .replace('"', "")
            .replace("«", "")
            .replace("»", "")
        )

        # --- سطر حماية إضافي (Regex) يمسح أي حرف صيني أو رموز غريبة تهرب من الـ AI ---
        # 2. تطبيق الفلتر النهائي (Regex) لضمان لغة عربية فقط وحذف أي "هبذ" صيني أو رموز غريبة
        hook_text = re.sub(r"[^\u0600-\u06FF\s\d\w?.!❤️🔥🌟🎬🍿]", "", hook_text)
    except Exception as e:
        print(f"⚠️ Groq Hook Error: {e}")
    # -------------------------------------------------------
    # --- [إعادة المتغيرات المحذوفة] ---
    # 1. إزالة النجوم (Markdown)
    clean_title_no_stars = clean_title.replace("*", "")

    # 1. ذكاء تحديد النوع (فيلم أم مسلسل)
    all_text_to_check = (raw_title + " " + str(row.get("labels", ""))).lower()
    is_movie = (
        "فيلم" in all_text_to_check
        or "movie" in all_text_to_check
        or content_type == "MOVIE"
    )

    # تصحيح النوع لو العنوان فيه كلمة "مسلسل" بشكل صريح
    if "مسلسل" in all_text_to_check or "series" in all_text_to_check:
        is_movie = False

    type_label = "🎞️ فيلم" if is_movie else "🌟 مسلسل"
    display_type = "أفلام" if is_movie else "مسلسلات"
    # 3. الهاشتاجات الثابتة
    # التعديل: اختيار الهاشتاجات الرائجة بناءً على نوع العمل
    if is_movie:
        trending_hashtags = "#سينما #افلام_جديدة #EgyPyramid"
    else:
        trending_hashtags = "#دراما #دراما_2026 #EgyPyramid"
    # 2. توليد الهاشتاجات الذكية مع تنظيفها من النوع المعاكس
    raw_labels = str(row.get("labels", "")).replace("،", ",")
    labels_list = [
        l.strip().replace(" ", "_").replace("(", "").replace(")", "")
        for l in raw_labels.split(",")
        if l.strip()
    ]

    # فلترة ذكية: لو مسلسل، امسح أي تاق فيه "أفلام" أو "فيلم" والعكس
    if is_movie:
        filtered_labels = [t for t in labels_list if "مسلسل" not in t.lower()]
    else:
        filtered_labels = [
            t for t in labels_list if "فيلم" not in t.lower() and "أفلام" not in t
        ]

    smart_hashtags = " ".join([f"#{tag}" for tag in filtered_labels[:3]])
    # 2. ذكاء تحديد اللغة
    # 2. ذكاء تحديد اللغة (منطق: عربي أصلي، مدبلج، أو مترجم)
    all_text_to_check = (raw_title + " " + str(row.get("labels", ""))).lower()

    # هل العنوان يحتوي على حروف عربية فقط (بدون حروف إنجليزية)؟
    has_english = bool(re.search(r"[a-zA-Z]", raw_title))

    if "مدبلج" in all_text_to_check or "dubbed" in all_text_to_check:
        lang_val = "دبلجة عربية احترافية 🎙️"
    elif "مترجم" in all_text_to_check or "subtitled" in all_text_to_check:
        lang_val = "لغة أصلية (مترجم) 📝"
    elif not has_english:
        # لو العنوان عربي خالص وما فيش كلمة "مترجم"، يبقى عمل عربي أصلي
        lang_val = "لغة عربية (أصلية) 🇪🇬"
    else:
        # لو العنوان إنجليزي (أو فيه إنجليزي) وما فيش علامة دبلجة، يبقى مترجم افتراضياً
        lang_val = "لغة أصلية (مترجم) 📝"

    # 3. تنظيف الهاشتاج الاحترافي (منع الالتصاق)
    hashtag_raw = (
        clean_title_no_stars.replace("-", " ").replace("(", " ").replace(")", " ")
    )
    hashtag_title = re.sub(r"[^\w\s]", "", hashtag_raw)  # حذف الرموز فقط
    hashtag_title = re.sub(
        r"\s+", "_", hashtag_title.strip()
    )  # تحويل كل الفراغات لـ _ واحدة
    # 4. تجميع الهاشتاجات ومنع التكرار
    all_tags = f"#{hashtag_title} {smart_hashtags} {trending_hashtags}"
    unique_hashtags = " ".join(dict.fromkeys(all_tags.split()))

    # 5. التمبلت النهائي المحدث
    final_output = f"""
🎬 {hook_text} 🎬

{type_label}: {clean_title_no_stars}
(جودة عالية Full HD 🔥)

📝 قصة العمل:
{short_story}

---
📌 التفاصيل:
📅 التاريخ: {human_date}
🎭 النوع: {display_type}
🔊 اللغة: {lang_val}

🍿 رابط {action_text} المباشر تجدونه في أول تعليق! 👇
---
{unique_hashtags}
    """
    print(f"📢 [Hook Generated]: {hook_text}")
    return final_output


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
