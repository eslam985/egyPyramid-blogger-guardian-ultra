import requests
import os
from datetime import datetime
import re
import json
from groq import Groq

# تعريف العميل باستخدام المفتاح الموجود في ملف .env
# هذا السطر هو الذي سيحل خطأ Undefined name "client_groq"
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client_groq = Groq(api_key=GROQ_API_KEY)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# استدعاء المفاتيح من ملف .env
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")


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
    short_story = story[:150].rsplit(" ", 1)[0] + "..." if len(story) > 150 else story

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
        5. لا تزد عن 15 كلمة."""

        completion = client_groq.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,  # خفض الـ temperature لـ 0.6 يضمن دقة لغوية أعلى
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

    type_label = "🎞️ فيلم" if content_type == "MOVIE" else "🌟 مسلسل"

    raw_labels = str(row.get("labels", "")).replace("،", ",")
    labels_list = [
        l.strip().replace(" ", "_").replace("(", "").replace(")", "")
        for l in raw_labels.split(",")
        if l.strip()
    ]
    smart_hashtags = " ".join([f"#{tag}" for tag in labels_list[:3]])

    # 1. إزالة النجوم (Markdown) لأن فيسبوك لا يدعمها وتظهر كرموز مزعجة
    clean_title_no_stars = clean_title.replace("*", "")

    # 2. تحسين الهاشتاجات لتكون أكثر رواجاً
    trending_hashtags = f"#سينما #افلام_جديدة #EgyPyramid"
    # تنظيف عنوان العمل لاستخدامه كهاشتاج (حذف الأقواس، النقط، والرموز)
    hashtag_title = re.sub(r"[^\w\s]", "", clean_title_no_stars).replace(" ", "_")
    # إذا كان العنوان يحتوي على "مدبلج"، نحدث اللغة تلقائياً
    if "مدبلج" in raw_title:
        lang_val = "دبلجة عربية احترافية 🎙️"
    else:
        lang_val = "لغة أصلية (مترجم) 📝"
    # التمبلت النهائي
    final_output = f"""
🎬 {hook_text} 🎬

{type_label}: {clean_title_no_stars}
(جودة عالية Full HD 🔥)

📝 قصة العمل:
{short_story}

---
📌 التفاصيل:
📅 التاريخ: {human_date}
🎭 النوع: {row.get('labels')}
🔊 اللغة: {lang_val}

🍿 رابط {action_text} المباشر تجدونه في أول تعليق! 👇
---
#{hashtag_title} {smart_hashtags} {trending_hashtags}
    """
    print(f"📢 [Hook Generated]: {hook_text}")  # عشان تتابع الـ AI طلع إيه
    return final_output


def send_to_telegram(photo_url, caption, post_url):
    """إرسال البوستر والتمبلت مع ضمان عدم الرفض من تليجرام"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ خطأ: مفاتيح تليجرام غير موجودة في الـ .env")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"

    # 1. قص النص لو طويل جداً (Telegram Limit 1024)
    safe_caption = caption[:1000] + "..." if len(caption) > 1000 else caption

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "photo": photo_url,
        "caption": safe_caption,
        # ملاحظة: شيلنا HTML mode عشان الهاشتاجات متبوظش الدنيا
        "reply_markup": json.dumps(
            {"inline_keyboard": [[{"text": "🍿 مشاهدة الآن", "url": post_url}]]}
        ),
    }

    try:
        response = requests.post(url, json=payload, timeout=15)
        if response.status_code == 200:
            print(f"✈️ تم إرسال إشعار تليجرام بنجاح.")
        else:
            print(f"⚠️ تليجرام رفض الإرسال: {response.text}")
    except Exception as e:
        print(f"⚠️ خطأ اتصال بتليجرام: {e}")


# اجعل المتغير يشير للدالة الحقيقية مباشرة
send_telegram_update = send_to_telegram
