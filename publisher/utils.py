import os
import re
import time
import requests
import random
from datetime import datetime
from dotenv import load_dotenv
from groq import Groq  # استيراد المكتبة
from deep_translator import GoogleTranslator

# 1. شحن المتغيرات
load_dotenv()

# 2. تهيئة الاتصال (الآن أصبح كائناً جاهزاً للاتصال)
client_groq = Groq(api_key=os.getenv("GROQ_API_KEY"))

# --- لا تغير أي شيء آخر في الدوال، التعديل أعلاه سيصلح الخطأ ---

# 2. استدعاء المفاتيح   
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


def ar_to_en(text):
    if not isinstance(text, str):
        return str(text)
    arabic_digits = "٠١٢٣٤٥٦٧٨٩"
    english_digits = "0123456789"
    translation_table = str.maketrans(arabic_digits, english_digits)
    return text.translate(translation_table)


def clean_for_match(t):
    if not t:
        return ""
    t = str(t).strip().lower()

    # 1. حذف السنة (أي 4 أرقام جنب بعض)
    t = re.sub(r"\d{4}", "", t)

    # 2. حذف أي حاجة بين قوسين (زي السنة أو الجودة)
    t = re.sub(r"\(.*?\)", "", t)

    # 3. حذف كلمة مسلسل/فيلم وكل الوصف
    for word in ["مسلسل", "فيلم", "مترجم", "مدبلج", "حصريا", "كامل", "مشاهدة", "تحميل"]:
        t = t.replace(word, "")

    # 4. حذف كلمة حلقة وما بعدها (عشان نقارن اسم المسلسل بس)
    t = re.sub(r"-\s*الحلقة.*|الحلقة.*", "", t)

    # 5. توحيد الحروف العربية الصعبة
    t = t.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    t = t.replace("ى", "ي").replace("ة", "ه")

    # 6. حذف أي رمز غير الحروف والأرقام (مسافات، شرط، نقط)
    t = re.sub(r"[^ا-يa-z0-9]", "", t)

    return t.strip()


# وظيفة تحويل العنوان لرابط إنجليزي نظيف
# وظيفة تحويل العنوان لرابط إنجليزي نظيف (نسخة مضمنة ومضمونة)
def generate_clean_slug(text):
    from deep_translator import GoogleTranslator  # استيراد محلي فقط

    try:
        # 1. ترجمة النص كاملاً
        translated = GoogleTranslator(source="auto", target="en").translate(text)

        # 2. الكلمات التي نريد حذفها لتقليل "البصمة" (Footprint)
        stop_words = [
            "watch",
            "series",
            "the",
            "all",
            "episodes",
            "dubbed",
            "translated",
            "hd",
            "full",
            "quality",
            "episode",
            "movie",
            "film",
        ]

        # 3. تنظيف النص وتحويل السنوات (مثلاً 2026 تصبح 26) لكسر البحث الآلي
        clean_text = translated.lower()
        clean_text = re.sub(r"20(\d{2})", r"\1", clean_text)  # يحول 2026 إلى 26
        clean_text = re.sub(r"[^a-z0-9\s]", "", clean_text)

        words = clean_text.split()

        # 4. فلترة الكلمات
        filtered_words = [w for w in words if w not in stop_words]

        # --- التطوير الأمني الجديد (التمويه الذكي) ---
        # إضافة كلمة تمويه عشوائية في بداية الرابط لكسر نمط "اسم الفيلم أولاً"
        safety_tags = ["egy", "prmd", "info", "net", "db"]
        random_tag = random.choice(safety_tags)

        # دمج الكلمات (الحد الأقصى 5 كلمات ليكون الرابط قوياً في السيو وغير مشبوه)
        slug_parts = [random_tag] + filtered_words[:5]

        slug = "-".join(slug_parts)
        # --- التعديل هنا لترى النتيجة في الكونسول ---
        print(f"🔗 [Slug] تم توليد الرابط بنجاح: {slug}")
        return slug

    except Exception as e:

        print(f"⚠️ فشلت الترجمة الذكية: {e}")
        return f"article-{int(time.time())}"


def convert_vk_to_embed(url):
    # 1. السماح بـ vk.com و vkvideo.ru
    if (
        not url
        or not any(domain in url for domain in ["vk.com", "vkvideo.ru"])
        or "video_ext.php" in url
    ):
        return url
    try:
        # 2. استخراج الـ OID والـ ID (يدعم الصيغتين)
        match_ids = re.search(r"video(-?\d+)_(\d+)", url)
        if not match_ids:
            return url

        fixed_oid = match_ids.group(1)
        fixed_id = match_ids.group(2)

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        # تقليل الـ timeout لسرعة السكريبت
        response = requests.get(url, headers=headers, timeout=10)

        # 3. بحث موسع عن الـ Hash
        hash_match = re.search(r"hash=([a-z0-9]+)", response.text)

        if hash_match:
            final_hash = hash_match.group(1)
            fixed_url = f"https://vkvideo.ru/video_ext.php?oid={fixed_oid}&id={fixed_id}&hash={final_hash}&hd=2"
            print(f"✅ [VK] تم استخراج وتصحيح الرابط: {fixed_url}")
            return fixed_url
        else:
            # محاولة أخيرة لو لم يجد الـ hash: إرجاع رابط الـ ext بدون hash (أحياناً يعمل)
            return f"https://vkvideo.ru/video_ext.php?oid={fixed_oid}&id={fixed_id}"

    except Exception as e:
        print(f"⚠️ فشل استخراج VK Hash: {e}")

    return url


def generate_seo_tags(title, labels_list):

    # تنظيف العنوان ليكون "الكلمة المفتاحية الخام"
    base_title = (
        title.replace("مشاهدة", "")
        .replace("مسلسل", "")
        .replace("جميع الحلقات", "")
        .replace("HD", "")
        .strip()
    )
    current_year = datetime.now().year

    # توزيع ذكي للكلمات
    tags = [
        f"تحميل {base_title} {current_year}",
        f"مشاهدة {base_title} اون لاين",
        f"{base_title} مترجم كامل",
        f"{base_title} EgyBest",
        f"{base_title} WeCima",
        f"حلقات {base_title} مدبلجة",
    ]

    # إضافة التصنيفات ككلمات مستقلة لزيادة الانتشار
    extra_keywords = [f"افلام {label}" for label in labels_list[:3]]
    all_tags = tags + extra_keywords

    # بناء الـ HTML مع تنظيف شامل (حذف الرموز واستبدال المسافات)
    # بناء الـ HTML البسيط جداً (فقط الوسوم بدون حاوية وبدون CSS)
    tags_html_list = []
    for tag in all_tags:
        clean_tag = re.sub(r"[^\w\s]", "", tag).strip().replace(" ", "_")
        # نرسل فقط الـ span بالكلاس الخاص به
        tags_html_list.append(f'<span class="seo-tag">#{clean_tag}</span>')

    # العودة بالنصوص فقط (هذه القيمة هي التي ستوضع مكان {{TAGS_CONTENT}} في قالبك)
    return " ".join(tags_html_list)


def generate_ai_seo_description(movie_title, story_summary):
    """صياغة وصف SEO احترافي باستخدام Groq (أسرع وأقوى بديل)"""
    title_clean = movie_title.split("[")[0].strip()

    # برومبت أكثر صرامة يمنع التكرار ويجبره على استخدام القصة
    prompt = (
        f"اكتب وصف بحث (Meta Description) لفيلم {title_clean}. "
        f"القصة: {story_summary}. "
        f"القواعد: 1. ابدأ بـ 'مشاهدة وتحميل  {title_clean} مترجم حصرياً بجودة عالية كامل'. "
        f"2. ادمج ملخص القصة فوراً بأسلوب جذاب. 3. ممنوع تكرار أي جملة. "
        f"4. الطول النهائي يجب أن يكون 150 حرفاً ولا يقل عن 145 حرفاً. 5. لا تضع مقدمات مثل 'إليك الوصف'."
        f"6. أضف جملة ختامية مشوقة مثل 'استمتع بمشاهدة الفيلم الآن بدون إعلانات مزعجة حصرياً لدينا'."
        f"7. ادخل الوصف باللغة العربية الفصحي او العامية المصرية فقط."
    )
    try:
        completion = client_groq.chat.completions.create(
            model="llama-3.3-70b-versatile",  # موديل جبار ومجاني
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,
            max_tokens=100,
        )
        ai_text = completion.choices[0].message.content.strip()
        # حذف علامات التنصيص بأنواعها
        # تنظيف النصوص الزائدة
        ai_text = (
            ai_text.replace('"', "").replace("«", "").replace("»", "").replace("'", "")
        )

        # --- فلتر عبقري لمنع تكرار الجمل (Double Check) ---
        sentences = ai_text.split(".")
        unique_sentences = []
        for s in sentences:
            if s.strip() and s.strip() not in unique_sentences:
                unique_sentences.append(s.strip())
        ai_text = ". ".join(unique_sentences)

        # حذف أي تكرار لكلمة "مشاهدة وتحميل" لو الـ AI استهبل وحطها مرتين
        if ai_text.count("مشاهدة وتحميل") > 1:
            first_index = ai_text.find("مشاهدة وتحميل")
            second_index = ai_text.find("مشاهدة وتحميل", first_index + 1)
            if second_index != -1:
                ai_text = ai_text[:second_index].strip()

        description = ai_text[:158].strip()
        print(f"📝 [SEO Desc]: {description}")
        return description
    except Exception as e:
        # كود الطوارئ (Fallback) المعدل لمنع التكرار
        clean_story = story_summary.replace("\n", " ").strip()
        print(f"⚠️ Groq Error: {e}")

        # تنظيف القصة وتقطيعها لجمل
        clean_story = story_summary.replace("\n", " ").strip()
        sentences = [s.strip() for s in clean_story.split(".") if len(s) > 20]

        # اختيار جملة عشوائية من القصة لضمان عدم التكرار نهائياً
        key_sentence = sentences[0] if sentences else clean_story[:100]

        templates = [
            f"مشاهدة فيلم {title_clean} مترجم بجودة عالية. تدور الأحداث حول: {key_sentence[:120]}... حصرياً على إيجي بيراميد.",
            f"تحميل {title_clean} كامل HD. قصة العمل: {key_sentence[:100]}... استمتع بمشاهدة سينمائية فريدة على موقعنا.",
            f"فيلم {title_clean} أون لاين. {key_sentence[:110]}... شاهد الآن مغامرة لا تنسى بجودة Full HD.",
        ]
        return random.choice(templates)
    except:
        return f"مشاهدة وتحميل فيلم {title_clean} مترجم بجودة عالية حصرياً على إيجي بيراميد."


def format_duration_iso(runtime_str):
    """تحويل وقت الفيلم (عربي أو إنجليزي) إلى تنسيق ISO 8601"""
    try:
        runtime_str = str(runtime_str).lower()
        # استخراج كافة الأرقام من النص (مثلاً: "1 ساعة و 38 دقيقة" تصبح ['1', '38'])
        numbers = re.findall(r"\d+", runtime_str)

        if not numbers:
            return "PT2H"  # قيمة افتراضية في حال الفشل

        # حالة وجود رقمين (ساعات ودقائق) - الترتيب دائماً ساعة ثم دقيقة
        if len(numbers) >= 2:
            return f"PT{numbers[0]}H{numbers[1]}M"

        # حالة وجود رقم واحد فقط
        if len(numbers) == 1:
            # لو النص يحتوي على 'ساعة' أو 'h' نعتبر الرقم ساعات
            if any(word in runtime_str for word in ["h", "ساعة", "ساعات"]):
                return f"PT{numbers[0]}H"
            # غير ذلك نعتبره دقائق (مثلاً: "90 دقيقة")
            else:
                return f"PT{numbers[0]}M"

        return "PT2H"
    except:
        return "PT2H"
