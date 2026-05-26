
#/media/es/DDrive/projects/apps-python/egyPyramid-guardian-ultra/downloader_new/metadata/ai_enricher.py

import re
import os
import json
import genai

from downloader_new.shared.logger import get_beast_logger

log = get_beast_logger("GuardianUltra")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
def get_metadata_via_ai(name, year):
    log.info(f"🤖 جاري استدعاء الذكاء الاصطناعي للبحث والتدقيق (Gemini Search)...")
    model = genai.GenerativeModel("gemini-2.5-flash")

    prompt = f"""
    Search strictly for the official Arabic metadata for: "{name}" ({year}).
    Required JSON format (Arabic only):
    {{
        "title": "اسم العمل الرسمي",
        "story": "قصة العمل الحقيقية بدقة (ابحث عن تفاصيل الشخصيات والأحداث الحقيقية)، إذا لم تجد معلومات مؤكدة ابحث باستخدام أسماء الأبطال المرتبطين بهذا الاسم)",
        "poster": "Direct URL to official poster",
        "labels": "Genre",
        "duration": "PT01H30M",
        "rating": "7.5",
        "runtime": "90 دقيقة",
        "year": "{year}"
    }}
    Important: Do NOT hallucinate or invent a story. If data is not found, return the name only in the story field as 'جاري تحديث البيانات'.
    """

    try:
        response = model.generate_content(prompt)

        # --- التعديل هنا: الاستخراج الآمن للـ JSON بعد الحصول على الاستجابة ---
        match = re.search(r"\{.*\}", response.text, re.DOTALL)
        if match:
            json_text = match.group()
        else:
            json_text = response.text.replace("```json", "").replace("```", "").strip()
        # -------------------------------------------------------

        data = json.loads(json_text)
        return (
            data.get("title"),
            data.get("story"),
            data.get("poster"),
            data.get("labels"),
            data.get("duration"),
            data.get("rating"),
            data.get("runtime"),
            data.get("year"),
        )
    except Exception as e:
        log.warning(f"❌ فشل الـ AI أيضاً: {e}")
        return None
