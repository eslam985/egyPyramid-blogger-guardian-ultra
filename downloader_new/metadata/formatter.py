# /media/es/DDrive/projects/apps-python/egyPyramid-guardian-ultra/downloader_new/metadata/formatter.py
import re
from urllib.parse import unquote
from downloader_new.shared.logger import get_beast_logger

log = get_beast_logger("formatter:")

def normalize_title(title, for_search=False, remove_year=True):
    if not title:
        return ""
    t = str(title).lower()
    # دي كانت ناقصة عندك وهي سبب كل التكرار اللي لقيناه
    t = t.replace("’", "'").replace("‘", "'").replace("´", "'").replace("`", "'")
    t = t.replace(":", " ").replace("—", " ").replace("–", " ") # شيل : خالص في الفحص
    
    if remove_year:
        t = re.sub(r"\b(19|20)\d{2}\b", " ", t)
    t = re.sub(r"\bs\d+\s*e\d+\b", " ", t, flags=re.I)
    t = re.sub(r"\bs\d+\b", " ", t, flags=re.I)
    t = re.sub(r"\be\d+\b", " ", t, flags=re.I)

    if for_search:
        t = re.sub(r"[^a-zA-Z0-9\u0600-\u06FF\s:\-']+", " ", t)
    else:
        # في فحص التكرار شيل كل حاجة وسيب حروف بس
        t = re.sub(r"[^a-zA-Z0-9\u0600-\u06FF\s]+", " ", t)

    # stop_words بتاعتك زي ما هي...
    stop_words = [
        "مترجمة",
        "مسلسل",
        "فيلم",
        "مترجم",
        "مدبلج",
        "كامل",
        "حصريا",
        "اونلاين",
        "مشاهدة",
        "تحميل",
        "بجودة",
        "عالية",
        "hd",
        "sd",
        "4k",
        "web-dl",
        "bluray",
        "season",
        "episode",
        "سيزون",
        "حلقة",
        "موسم",
        "اون",
        "لاين",
    ]
    for w in stop_words:
        t = re.sub(rf"\b{w}\b", " ", t)

    t = " ".join(t.split())
    return t



def get_clean_media_data(raw_name):
    raw_name = str(raw_name)
    # 1. أنماط استخراج الموسم والحلقة
    # نمط S01E05 أو S1E5
    s_e_pattern = re.search(r"[sS](\d+)[eE](\d+)", raw_name)
    # نمط الموسم X الحلقة Y (بالعربية)
    ar_s_e_pattern = re.search(
        r"(?:الموسم|موسم)\s*(\d+).*?(?:الحلقة|حلقة|ح)\s*(\d+)", raw_name
    )
    # نمط الحلقة X فقط (يفترض الموسم 1)
    ep_only_pattern = re.search(r"(?:الحلقة|حلقة|ح)\s*(\d+)", raw_name)
    # نمط الموسم X فقط
    season_only_pattern = re.search(r"(?:الموسم|موسم)\s*(\d+)", raw_name)

    category = "movie"
    season_no = 1
    ep_no = 1
    clean_title = raw_name

    if s_e_pattern:
        category = "tv"
        season_no = int(s_e_pattern.group(1))
        ep_no = int(s_e_pattern.group(2))
        clean_title = re.split(r"[sS]\d+[eE]\d+", raw_name)[0]
    elif ar_s_e_pattern:
        category = "tv"
        season_no = int(ar_s_e_pattern.group(1))
        ep_no = int(ar_s_e_pattern.group(2))
        clean_title = re.split(r"(?:الموسم|موسم)\s*\d+", raw_name)[0]
    elif ep_only_pattern:
        category = "tv"
        ep_no = int(ep_only_pattern.group(1))
        # التحقق إذا كان هناك موسم مذكور في مكان آخر
        if season_only_pattern:
            season_no = int(season_only_pattern.group(1))
            clean_title = re.split(r"(?:الموسم|موسم)\s*\d+", raw_name)[0]
        else:
            clean_title = re.split(r"(?:الحلقة|حلقة|ح)\s*\d+", raw_name)[0]
    elif season_only_pattern:
        category = "tv"
        season_no = int(season_only_pattern.group(1))
        clean_title = re.split(r"(?:الموسم|موسم)\s*\d+", raw_name)[0]
    elif re.search(
        r"(?:\bseries\b|\bseason\b|\bepisode\b|\bS\d+E\d+\b|مسلسل|موسم|الموسم|حلقة)",
        raw_name,
        re.IGNORECASE,
    ):
        category = "tv"
        clean_title = raw_name
    # تنظيف العنوان النهائي باستخدام دالة normalize_title
    clean_title = normalize_title(clean_title)

    return clean_title, category, season_no, ep_no


def extract_clean_media_info(raw_name: str) -> tuple:
    """
    تنظيف اسم الميديا واستخراج السنة منه.
    تعيد (clean_name, extracted_year).
    تتعامل مع روابط topcinema.rip.
    """
    if "topcinema.rip" in str(raw_name):
        decoded = unquote(str(raw_name))
        match = re.search(r"فيلم-(.*?)-مترجم", decoded)
        raw_name = (
            match.group(1).replace("-", " ").title()
            if match
            else decoded.split("/")[-2].replace("-", " ").replace("فيلم", "").title()
        )

    original_task_name = str(raw_name).strip()
    year_match = re.search(r"\b((?:19|20)\d{2})\b", original_task_name)
    extracted_year = year_match.group(1) if year_match else None

    return original_task_name, extracted_year



def build_display_title(original_task_name: str, tmdb_title: str, season_ep_info=None) -> str:
    """
    بناء الاسم المعروض النهائي مع إضافة معلومات الموسم والحلقة إذا وُجدت.
    season_ep_info: قاموس اختياري يحتوي على season و/أو episode.
    """
    display_title = tmdb_title if tmdb_title else original_task_name

    if "الموسم" in original_task_name and "الموسم" not in display_title:
        season_match = re.search(r"(الموسم\s*\d+)", original_task_name)
        if season_match:
            display_title = display_title + " " + season_match.group(1)

    if "الحلقة" in original_task_name and "الحلقة" not in display_title:
        ep_match = re.search(r"(الحلقة\s*\d+|ح\s*\d+)", original_task_name)
        if ep_match:
            display_title = display_title + " " + ep_match.group(1)

    if season_ep_info:
        season = season_ep_info.get("season")
        episode = season_ep_info.get("episode")
        if season and "الموسم" not in display_title:
            display_title = f"{display_title} الموسم {season}"
        if episode and "الحلقة" not in display_title:
            display_title = f"{display_title} الحلقة {episode}"

    return display_title
