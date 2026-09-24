"""
tmdb_client.py
==============
Client موحد للتعامل مع TMDB و OMDb APIs.
مبني على مبدأ فصل المسؤوليات: كل دالة مسؤولة عن حاجة واحدة بس.
"""

import re
import os
import requests
import json
from deep_translator import GoogleTranslator

from downloader_new.shared.logger import get_beast_logger
from downloader_new.metadata.images import upload_poster_to_cloudinary
from downloader_new.shared.helpers import minutes_to_iso, is_mostly_english
from downloader_new.db.supabase_client import is_media_data_complete

log = get_beast_logger("tmdb_client.py")
translator = GoogleTranslator(source="auto", target="ar")

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
OMDB_API_KEY = os.getenv("OMDB_API_KEY")

TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/original"
OMDB_BASE_URL = "http://www.omdbapi.com"
IMDB_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/1.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GENRE_MAP = {
    "Action": "أكشن",
    "Adventure": "مغامرة",
    "Animation": "رسوم متحركة",
    "Comedy": "كوميديا",
    "Crime": "جريمة",
    "Documentary": "وثائقي",
    "Drama": "دراما",
    "Family": "عائلي",
    "Fantasy": "فانتازيا",
    "History": "تاريخ",
    "Horror": "رعب",
    "Music": "موسيقى",
    "Mystery": "غموض",
    "Romance": "رومانسي",
    "Science Fiction": "خيال علمي",
    "TV Movie": "فيلم تلفزيوني",
    "Thriller": "إثارة",
    "War": "حرب",
    "Western": "غرب أمريكي",
    "Sport": "رياضة",
    "Short": "قصير",
    "Sci-Fi": "خيال علمي",
    "Biography": "سيرة شخصية",
    "German": "ألماني",
    "French": "فرنسي",
    "Japanese": "ياباني",
    "Whodunnit": "من فعلها",
    "Superhero": "سوبرهيرو",
    "Cyberpunk": "سايبربانك",
}

TV_KEYWORDS = {
    "مسلسل",
    "موسم",
    "حلقة",
    "Series",
    "Season",
    "Episode",
    "TV",
    "tv",
    "season",
    "episode",
}

DRAMABOX_DOMAIN = "dramaboxdb.com"

DEFAULT_METADATA = {
    "tmdb_id": None,
    "display_title": "",
    "story": "لا يوجد وصف",
    "poster": "",
    "labels": "أفلام",
    "duration": "PT01H30M",
    "rating": "N/A",
    "runtime": "غير محدد",
    "year": "غير محدد",
}



# ===========================================================================
# Section 1: Input Parsing — استخراج وتحليل المدخل
# ===========================================================================

def is_url_or_id(query: str) -> bool:
    """هل المدخل رابط أو ID مباشر؟"""
    return "http" in query or query.startswith(("tt", "tmdb"))


def extract_year_from_query(query: str) -> str | None:
    """استخراج سنة الإنتاج من نص البحث."""
    match = re.search(r"(\d{4})", query)
    return match.group(1) if match else None


def clean_query_from_year(query: str) -> str:
    """إزالة السنة وعلامات الترقيم الزائدة من نص البحث."""
    return re.sub(r"\d{4}", "", query).replace(":", "").replace("_", " ").strip()


def detect_content_type(query: str) -> str:
    """تحديد نوع المحتوى: فيلم أو مسلسل بناءً على الكلمات المفتاحية."""
    return "tv" if any(kw in query for kw in TV_KEYWORDS) else "movie"


def extract_id_from_input(query: str) -> tuple[str | None, str | None]:
    """
    استخراج الـ ID ونوع المحتوى من المدخل (رابط أو نص).
    تُعيد: (media_id, content_type) أو (None, None) لو مفيش ID.
    """
    if "imdb.com/title/" in query:
        match = re.search(r"(tt\d+)", query)
        return (match.group(1), None) if match else (None, None)

    if "themoviedb.org/movie/" in query:
        match = re.search(r"/movie/(\d+)", query)
        return (match.group(1), "movie") if match else (None, None)

    if "themoviedb.org/tv/" in query:
        match = re.search(r"/tv/(\d+)", query)
        return (match.group(1), "tv") if match else (None, None)

    if "omdbapi.com" in query:
        match = re.search(r"[iI]=(tt\d+)", query)
        return (match.group(1), None) if match else (None, None)

    if query.startswith("tt"):
        return query, None

    if query.startswith("tmdb-tv-"):
        return query.replace("tmdb-tv-", ""), "tv"

    if query.startswith("tmdb-"):
        return query.replace("tmdb-", ""), "movie"

    if query.startswith("tmdb"):
        return re.sub(r"[^0-9]", "", query), "movie"

    return None, None


def build_fallback_title_from_url(url: str) -> str:
    """استخراج اسم قابل للقراءة من رابط URL في حالة الفشل."""
    name = url.split("/")[-1].split("?")[0]
    name = name.replace("-", " ").replace("_", " ").title()
    return re.sub(r"^\d+-", "", name).strip() or url


# ===========================================================================
# Section 2: TMDB API Calls — طلبات TMDB
# ===========================================================================
def extract_imdb_id_from_trailer(trailer_url: str) -> str | None:
    """
    يستخرج ttxxxx من صفحة فيديو IMDb.
    """

    if not trailer_url:
        return None

    try:
        r = requests.get(
            trailer_url,
            headers=IMDB_HEADERS,
            timeout=20,
        )

        if r.status_code != 200:
            return None

        match = re.search(r'"primaryTitle":\{"id":"(tt\d+)"', r.text)

        if match:
            imdb_id = match.group(1)
            log.info(f"🎬 Trailer كشف IMDb ID = {imdb_id}")
            return imdb_id

    except Exception as e:
        log.warning(f"Trailer lookup failed: {e}")

    return None


def resolve_tmdb_id_from_imdb(imdb_id: str) -> tuple[str | None, str | None]:
    """تحويل IMDb ID إلى TMDB ID مع تحديد نوع المحتوى."""
    url = (
        f"{TMDB_BASE_URL}/find/{imdb_id}?api_key={TMDB_API_KEY}&external_source=imdb_id"
    )
    data = requests.get(url).json()

    if data.get("movie_results"):
        return data["movie_results"][0]["id"], "movie"
    if data.get("tv_results"):
        return data["tv_results"][0]["id"], "tv"
    return None, None


def search_tmdb(query: str, content_type: str, year: str | None) -> str | None:
    """
    البحث في TMDB بالاسم والسنة.
    تُعيد الـ TMDB ID الأدق تطابقاً، أو None لو مفيش.
    """
    url = f"{TMDB_BASE_URL}/search/{content_type}?api_key={TMDB_API_KEY}&query={query}&language=ar"
    if year:
        url += f"&year={year}"

    results = requests.get(url).json().get("results", [])
    if not results:
        return None

    query_lower = query.lower()
    for result in results:
        result_title = (result.get("name") or result.get("title") or "").lower()
        if query_lower in result_title or result_title in query_lower:
            return result["id"]

    log.warning(f"⚠️ TMDB أعاد نتائج غير مطابقة للاسم: {query}")
    return None


def fetch_tmdb_details(tmdb_id: str, content_type: str, language: str = "en") -> dict:
    """جلب تفاصيل عمل معين من TMDB بلغة محددة."""
    url = f"{TMDB_BASE_URL}/{content_type}/{tmdb_id}?api_key={TMDB_API_KEY}&language={language}"
    return requests.get(url).json()


def resolve_tmdb_id(
    query: str, media_id: str | None, content_type: str | None, year: str | None
) -> tuple[str | None, str]:
    """
    الخطوة المركزية لتحديد الـ TMDB ID النهائي.
    تُعيد: (tmdb_id, content_type).
    """
    # لو عندنا ID جاهز
    if media_id:
        if str(media_id).startswith("tt"):
            tmdb_id, resolved_type = resolve_tmdb_id_from_imdb(media_id)
            return tmdb_id, resolved_type or content_type or "movie"
        return media_id, content_type or "movie"

    # لو محتاجين نبحث
    detected_type = content_type or detect_content_type(query)
    clean_q = clean_query_from_year(query)
    tmdb_id = search_tmdb(clean_q, detected_type, year)
    return tmdb_id, detected_type


# ===========================================================================
# Section 3: OMDb API Calls — طلبات OMDb
# ===========================================================================


def fetch_omdb_data(query: str, year: str) -> dict | None:
    """
    البحث في OMDb بالاسم والسنة.
    تُعيد البيانات الخام من OMDb أو None لو مفيش تطابق.
    """
    clean_q = clean_query_from_year(query)
    omdb_query = clean_q.replace(" ", "+")
    url = f"{OMDB_BASE_URL}/?apikey={OMDB_API_KEY}&t={omdb_query}&y={year}"

    try:
        data = requests.get(url).json()
    except Exception as e:
        log.error(f"⚠️ خطأ أثناء الاتصال بـ OMDb: {e}")
        return None

    if data.get("Response") != "True":
        return None

    # تحقق من تطابق الاسم
    omdb_title = data.get("Title", "").lower()
    first_word = clean_q.strip().split(" ")[0].lower()
    if first_word not in omdb_title:
        log.warning(
            f"🛑 رفض النتيجة: OMDb أعاد '{omdb_title}' وهي لا تطابق '{clean_q}'"
        )
        return None

    return data


# ===========================================================================
# Section 4: Data Processing — معالجة وتحويل البيانات
# ===========================================================================


def translate_text(text: str) -> str:
    """ترجمة نص للعربية مع معالجة الأخطاء."""
    if not text or text == "N/A":
        return "لا يوجد وصف"
    try:
        return translator.translate(text)
    except Exception:
        return text


def translate_genres(raw_genres: str) -> str:
    """ترجمة قائمة التصنيفات المفصولة بفواصل."""
    genres = [g.strip() for g in raw_genres.split(",")]
    return ", ".join(GENRE_MAP.get(g, g) for g in genres)


def parse_runtime(raw_runtime: str) -> tuple[str, str]:
    """
    تحويل وقت التشغيل الخام لـ ISO format ونص عربي مقروء.
    تُعيد: (duration_iso, runtime_str).
    """
    if not raw_runtime or raw_runtime == "N/A":
        return "PT01H30M", "غير محدد"

    match = re.search(r"(\d+)", raw_runtime)
    if not match:
        return "PT01H30M", "غير محدد"

    minutes = int(match.group(1))
    duration = f"PT{minutes // 60:02d}H{minutes % 60:02d}M"
    hours, mins = minutes // 60, minutes % 60

    if hours > 0:
        runtime_str = f"{hours} ساعة و {mins} دقيقة"
    else:
        runtime_str = f"{minutes} دقيقة"

    return duration, runtime_str


def parse_runtime_minutes(minutes: int) -> tuple[str, str]:
    """نفس parse_runtime لكن المدخل رقم دقائق مش نص."""
    if not minutes:
        return "PT01H30M", "غير محدد"
    duration = minutes_to_iso(minutes)
    hours, mins = minutes // 60, minutes % 60
    runtime_str = f"{hours} ساعة و {mins} دقيقة" if hours > 0 else f"{minutes} دقيقة"
    return duration, runtime_str


def resolve_story(ar_data: dict, en_data: dict) -> str:
    """
    اختيار القصة الأنسب: عربي أولاً، لو مفيش نترجم الإنجليزي.
    """
    ar_story = ar_data.get("overview", "").strip()
    if ar_story:
        return ar_story

    en_story = en_data.get("overview", "")
    return translate_text(en_story) if en_story else "لا يوجد وصف"


def resolve_title(original_input: str, en_data: dict, ar_data: dict) -> str:
    """
    اختيار العنوان الأنسب بناءً على لغة المدخل الأصلي.
    """
    if is_mostly_english(original_input) or is_url_or_id(original_input):
        title = en_data.get("title") or en_data.get("name")
        fallback = ar_data.get("title") or ar_data.get("name")
    else:
        title = ar_data.get("title") or ar_data.get("name")
        fallback = en_data.get("title") or en_data.get("name")

    result = title or fallback
    if not result or "http" in str(result):
        result = build_fallback_title_from_url(original_input)

    return result


def resolve_genres_from_tmdb(ar_data: dict) -> str:
    """استخراج التصنيفات العربية من بيانات TMDB."""
    genres = ar_data.get("genres", [])
    if not genres:
        return "أفلام"
    return ", ".join(g["name"] for g in genres)


def resolve_poster(poster_path: str | None) -> str:
    """بناء رابط البوستر الكامل من المسار الجزئي."""
    if not poster_path:
        return ""
    return f"{TMDB_IMAGE_BASE}{poster_path}"


# ===========================================================================
# Section 5: Special Cases — الحالات الخاصة
# ===========================================================================


def handle_dramabox(url: str) -> dict:
    """معالجة روابط DramaBox بشكل مباشر بدون API."""
    log.info("⚡ DramaBox detected: Direct Fallback...")
    title = url.split("/")[-1].replace("-", " ").title()
    return {
        **DEFAULT_METADATA,
        "tmdb_id": None,
        "display_title": title,
        "story": "وصف تلقائي (DramaBox Archive)",
        "labels": "DramaBox",
        "duration": "PT01H00M",
        "rating": "8.5",
    }


def build_fallback_result(original_input: str, year: str | None) -> dict:
    """بناء نتيجة احتياطية لما يفشل كل شيء."""
    log.warning(f"🛑 لم يتم العثور على تطابق رسمي لـ '{original_input}'.")

    if is_url_or_id(original_input):
        title = build_fallback_title_from_url(original_input)
    else:
        title = original_input

    return {
        **DEFAULT_METADATA,
        "display_title": title or original_input,
        "year": year or "غير محدد",
    }


# ===========================================================================
# Section 6: OMDb Result Builder — تجميع نتيجة OMDb
# ===========================================================================

def build_metadata_from_omdb(
    omdb_data: dict, year: str | None, original_input: str | None = None
) -> dict:
    """تحويل بيانات OMDb الخام لـ metadata dict موحد."""
    imdb_id = omdb_data.get("imdbID")
    if imdb_id:
        title = omdb_data.get("Title", "")
        release_year = omdb_data.get("Year", year or "N/A")

        db_check = is_media_data_complete(imdb_id, title, release_year)
        if db_check.get("exists"):
            if db_check.get("is_complete"):
                log.info(
                    "⚡ قاعدة البيانات: تم العثور على العمل مكتمل البيانات "
                    f"(تخطي جلب البيانات ورفع الصورة): {original_input or title or 'unknown'}"
                )
                media = db_check["data"]
                return {
                    "tmdb_id": media.get("tmdb_id"),
                    "display_title": media.get("title"),       # Not Null in DB
                    "story": media.get("story"),               # Nullable
                    "poster": media.get("poster_url"),         # Nullable
                    "labels": media.get("labels"),             # Nullable
                    "duration": media.get("duration_iso"),     # Nullable
                    "rating": media.get("rating"),             # Nullable
                    "runtime": media.get("runtime"),           # Nullable
                    "year": media.get("year")                  # Not Null in DB
                }

    story = translate_text(omdb_data.get("Plot", ""))
    labels = translate_genres(omdb_data.get("Genre", "أفلام"))
    duration, runtime_str = parse_runtime(omdb_data.get("Runtime", "N/A"))

    raw_rating = omdb_data.get("imdbRating", "0")
    rating = str(raw_rating) if raw_rating != "N/A" else "0.0"
    release_year = omdb_data.get("Year", year or "N/A")

    poster_url = omdb_data.get("Poster")
    if poster_url and poster_url != "N/A":
        log.info("☁️ جاري رفع بوستر IMDb (عبر OMDb) لكلاود ناري...")
        poster_url = upload_poster_to_cloudinary(poster_url)
    else:
        poster_url = ""

    result = {
        "tmdb_id": omdb_data.get("imdbID"),
        "display_title": omdb_data.get("Title", ""),
        "story": story,
        "poster": poster_url,
        "labels": labels,
        "duration": duration,
        "rating": rating,
        "runtime": runtime_str,
        "year": release_year,
    }

    return result


# ===========================================================================
# Section 7: TMDB Result Builder — تجميع نتيجة TMDB
# ===========================================================================


def build_metadata_from_tmdb(
    tmdb_id: str, content_type: str, original_input: str
) -> dict:
    """جلب وتحويل بيانات TMDB الكاملة لـ metadata dict موحد."""
    db_check = is_media_data_complete(tmdb_id, original_input, None)
    if db_check.get("exists"):
        if db_check.get("is_complete"):
            media = db_check["data"]
            title_in_db = media.get("title") or original_input
            log.info(
                "⚡ قاعدة البيانات: تم العثور على العمل مكتمل البيانات "
                f"(تخطي جلب البيانات ورفع الصورة): {title_in_db}"
            )
            return {
                "tmdb_id": media.get("tmdb_id"),
                "display_title": media.get("title"),       # Not Null in DB
                "story": media.get("story"),               # Nullable
                "poster": media.get("poster_url"),         # Nullable
                "labels": media.get("labels"),             # Nullable
                "duration": media.get("duration_iso"),     # Nullable
                "rating": media.get("rating"),             # Nullable
                "runtime": media.get("runtime"),           # Nullable
                "year": media.get("year")                  # Not Null in DB
            }

    en_data = fetch_tmdb_details(tmdb_id, content_type, language="en")
    ar_data = fetch_tmdb_details(tmdb_id, content_type, language="ar")

    title = resolve_title(original_input, en_data, ar_data)
    story = resolve_story(ar_data, en_data)
    labels = resolve_genres_from_tmdb(ar_data)

    raw_rating = en_data.get("vote_average", 0.0)
    rating = str(round(raw_rating, 1)) if raw_rating > 0 else "N/A"

    release_date = (
        en_data.get("release_date") or en_data.get("first_air_date") or "0000"
    )
    release_year = release_date[:4]

    runtime_minutes = en_data.get("runtime")
    if not runtime_minutes:
        runtime_list = en_data.get("episode_run_time", [])
        runtime_minutes = runtime_list[0] if runtime_list else None

    duration, runtime_str = parse_runtime_minutes(runtime_minutes)

    poster_path = en_data.get("poster_path")
    raw_poster_url = resolve_poster(poster_path)

    log.info("☁️ جاري معالجة بوستر TMDB ورفعه لكلاود ناري...")
    final_poster = upload_poster_to_cloudinary(raw_poster_url) if raw_poster_url else ""

    log.info(f"✅ تم العثور على الاسم الرسمي: {title}")

    result = {
        "tmdb_id": tmdb_id,
        "display_title": title,
        "story": story,
        "poster": final_poster,
        "labels": labels,
        "duration": duration,
        "rating": rating,
        "runtime": runtime_str,
        "year": release_year,
    }

    return result


# ===========================================================================
# Section 8: Local Radar — الفهرس المحلي
# ===========================================================================


def check_local_radar(query: str, year: str | None) -> str | None:
    """فحص الفهرس المحلي لجلب الـ ID قبل البحث الخارجي."""
    try:
        from downloader_new.metadata.local_lookup import search_local_imdb

        return search_local_imdb(query, year)
    except Exception as e:
        log.error(f"❌ خطأ في الرادار المحلي: {e}")
        return None


# ===========================================================================
# Section 9: Main Orchestrator — المنسق الرئيسي
# ===========================================================================


def get_movie_data(name: str, year: str | None = None) -> tuple:
    """
    النقطة الرئيسية للجلب: تنسق بين كل المصادر وتُعيد tuple بالبيانات.
    الترتيب: Trailer ID → Local Radar → TMDB → OMDb → Fallback.
    """
    query = str(name).strip()

    # -------------------------------------------------
    # DramaBox
    # -------------------------------------------------
    if DRAMABOX_DOMAIN in query:
        result = handle_dramabox(query)
        return _dict_to_tuple(result)

    # استخراج الـ ID والسنة من المدخل
    media_id, content_type = extract_id_from_input(query)

    if is_url_or_id(query):
        final_year = None
        search_query = query
    else:
        final_year = year or extract_year_from_query(query)
        search_query = clean_query_from_year(query)

    # المرحلة الأولى: TMDB
    tmdb_id, resolved_type = resolve_tmdb_id(
        search_query, media_id, content_type, final_year
    )

    if tmdb_id:
        try:
            result = build_metadata_from_tmdb(
                str(tmdb_id), resolved_type or "movie", query
            )
            return _dict_to_tuple(result)
        except Exception as e:
            log.error(f"⚠️ خطأ في بناء بيانات TMDB: {e}")

    # المرحلة الثانية: OMDb (لو TMDB فشل وعندنا سنة)
    if final_year:
        log.warning(f"⚠️ TMDB فشل.. جاري فحص OMDb بالسنة: {final_year}")
        omdb_data = fetch_omdb_data(search_query, final_year)
        if omdb_data:
            result = build_metadata_from_omdb(omdb_data, final_year)
            return _dict_to_tuple(result)

    # المرحلة الثالثة: Fallback
    result = build_fallback_result(query, final_year)
    return _dict_to_tuple(result)


def _dict_to_tuple(metadata: dict) -> tuple:
    """تحويل metadata dict للـ tuple القديم للتوافق مع الكود الموجود."""
    return (
        metadata["tmdb_id"],
        metadata["display_title"],
        metadata["story"],
        metadata["poster"],
        metadata["labels"],
        metadata["duration"],
        metadata["rating"],
        metadata["runtime"],
        metadata["year"],
    )


# ===========================================================================
# Section 10: Public API — الواجهة العامة للملف
# ===========================================================================


def fetch_tmdb_metadata(search_query: str, year: str | None = None, trailer_url: str | None = None) -> dict:
    """
    الواجهة العامة: جلب بيانات الميديا كـ dict.
    تعيد قاموساً بالمفاتيح: tmdb_id, display_title, story, poster,
    labels, duration, rating, runtime, year.
    """
    log.info(f"🔍 جلب بيانات العمل من TMDB/IMDB...")
    log.info(f"🔎 البحث عن: {search_query} " + (f"({year})" if year else "") + " ...")

    effective_query = search_query

    # 1. محاولة استخراج الـ ID من رابط التريلر أولاً (المصدر الأكثر دقة)
    if trailer_url and "imdb.com/video" in trailer_url:
        log.info(f"🎬 جاري فحص رابط التريلر: {trailer_url}")
        trailer_id = extract_imdb_id_from_trailer(trailer_url)
        if trailer_id:
            log.info(f"✨ تم استخراج ID من التريلر: {trailer_id}. سيتم استخدامه مباشرة.")
            effective_query = trailer_id
        else:
            log.warning("⚠️ فشل استخراج الـ ID من التريلر.")

    # 2. محاولة الفهرس المحلي فقط إذا لم نحصل على ID من التريلر
    if not effective_query.startswith("tt"):
        local_id = check_local_radar(search_query, year)
        if local_id:
            log.info(f"✨ تم العثور على ID محلي: {local_id}. سيتم استخدامه مباشرة.")
            effective_query = local_id

    log.debug(f"DEBUG: calling get_movie_data with '{effective_query}'")
    movie_result = get_movie_data(effective_query, year=year)
    log.debug(f"DEBUG: get_movie_data returned: {movie_result}")

    if isinstance(movie_result, (list, tuple)) and len(movie_result) >= 9:
        keys = [
            "tmdb_id",
            "display_title",
            "story",
            "poster",
            "labels",
            "duration",
            "rating",
            "runtime",
            "year",
        ]
        return dict(zip(keys, movie_result[:9]))

    log.warning(
        f"⚠️ بيانات ناقصة أو غير صالحة لـ '{search_query}'، سيتم استخدام الافتراضي."
    )
    return {**DEFAULT_METADATA, "display_title": search_query, "year": year or "N/A"}
