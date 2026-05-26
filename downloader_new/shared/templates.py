# /media/es/DDrive/projects/apps-python/egyPyramid-guardian-ultra/downloader_new/shared/templates.py
import re
import os
from groq import Groq

# تعريف العميل باستخدام المفتاح الموجود في ملف .env
# هذا السطر هو الذي سيحل خطأ Undefined name "client_groq"
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# إنشاء العميل فقط إذا كان المفتاح موجوداً لتجنب انهيار الاستيراد
client_groq = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

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

    # --- ذكاء تحديد النوع (المطور) ---
    all_text_to_check = (raw_title + " " + str(row.get("labels", ""))).lower()

    # 1. التحقق من الـ labels القادمة من TMDB (الأكثر دقة)
    # عادة TMDB يضع "أفلام" أو "TV Series"
    is_movie_label = any(
        word in all_text_to_check for word in ["فيلم", "أفلام", "movie"]
    )

    # 2. التحقق من content_type الممرر من سكرابيت التحميل
    # (نحولها لـ lower للتأكد من المطابقة)
    is_movie_type = str(content_type).lower() == "movie"

    # المنطق النهائي: هو فيلم إذا وجدنا كلمة فيلم OR إذا كان النوع القادم من المحرك "movie"
    # بشرط ألا يحتوي العنوان على كلمة "مسلسل" أو "حلقة"
    is_movie = is_movie_label or is_movie_type

    if any(
        word in all_text_to_check
        for word in ["مسلسل", "حلقة", "موسم", "series", "episode"]
    ):
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