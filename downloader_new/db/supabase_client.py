"""
supabase_client.py
==================
طبقة البيانات الموحدة للتعامل مع Supabase.
مبني على مبدأ فصل المسؤوليات: كل دالة مسؤولة عن جدول واحد أو عملية واحدة.
"""

import re
import os
import time
from typing import Optional

from supabase import create_client, Client as SupabaseClient

from downloader_new.shared.logger import get_beast_logger
from downloader_new.metadata.formatter import normalize_title

log = get_beast_logger("supabase_client.py")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    log.error("❌ خطأ: لم يتم العثور على مفاتيح Supabase في متغيرات البيئة!")

supabase: SupabaseClient = create_client(SUPABASE_URL, SUPABASE_KEY)

# قيم لا معنى لها عند الحفظ في DB
_USELESS_VALUES = [None, "", "لا يوجد وصف", "جاري تحديث القصة...", "N/A", "غير محدد"]

RETRY_COUNT    = 3
RETRY_DELAY    = 3  # ثواني


# ===========================================================================
# Section 1: Core Utilities — أدوات مساعدة أساسية
# ===========================================================================

def _retry(fn, label: str = ""):
    """
    تنفيذ دالة مع إعادة المحاولة تلقائياً عند فشل Supabase (502/Timeout).
    يرمي الخطأ بعد استنفاد كل المحاولات.
    """
    for attempt in range(RETRY_COUNT):
        try:
            return fn()
        except Exception as e:
            if attempt < RETRY_COUNT - 1:
                log.warning(f"⚠️ [{label}] سوبابيز متعثر، محاولة {attempt + 1}... ({e})")
                time.sleep(RETRY_DELAY)
            else:
                raise e


def _clean_payload(payload: dict) -> dict:
    """حذف القيم الفارغة أو عديمة الفائدة وروابط الـ Placeholder من الـ payload."""
    return {
        k: v
        for k, v in payload.items()
        if v not in _USELESS_VALUES and "via.placeholder.com" not in str(v)
    }


def _build_slug(title: str) -> str:
    """توليد slug نظيف من العنوان — بدون أرقام موسم/حلقة."""
    from downloader_new.metadata.formatter import get_clean_media_data
    clean = get_clean_media_data(title)
    clean_title = clean[0] if (clean and len(clean) == 4) else title
    
    slug = clean_title.lower().strip().replace(" ", "-")
    slug = re.sub(r"[^a-z0-9\u0600-\u06FF-]", "", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug


def _resolve_final_title(original_task_name: str, c_title: str) -> str:
    """
    اختيار العنوان النهائي للحفظ.
    المهم: نرجع عنوان الـ SERIES فقط، مش عنوان الحلقة.
    """
    if original_task_name and not original_task_name.startswith(("http://", "https://")):
        # نستخرج عنوان المسلسل فقط بدون رقم الموسم/الحلقة
        from downloader_new.metadata.formatter import get_clean_media_data
        clean = get_clean_media_data(original_task_name)
        if clean and len(clean) == 4:
            return clean[0]  # c_title النظيف بدون أرقام
        return original_task_name
    return c_title


# ===========================================================================
# Section 2: Media Lookup — البحث عن الميديا
# ===========================================================================

def _find_media_by_tmdb_id(tmdb_id: str) -> Optional[dict]:
    """البحث عن الميديا بالـ TMDB ID."""
    res = supabase.table("medias").select("*").eq("tmdb_id", str(tmdb_id)).execute()
    return res.data[0] if res.data else None


def _find_media_by_exact_title(title: str, year: Optional[str]) -> Optional[dict]:
    """البحث عن الميديا بالعنوان والسنة المطابقين تماماً."""
    query = supabase.table("medias").select("*").eq("title", title)
    if year:
        query = query.eq("year", str(year))
    res = query.execute()
    return res.data[0] if res.data else None


def _find_media_by_smart_pattern(title: str, year: Optional[str]) -> Optional[dict]:
    """
    البحث المرن بـ LIKE pattern للأعمال العربية أو ذات الأسماء غير الدقيقة.
    يُعيد أول تطابق دقيق بعد مقارنة العناوين المُنقّاة.
    """
    smart_pattern = re.sub(r"[^a-zA-Z0-9\u0600-\u06FF]+", "%", normalize_title(title))
    res = supabase.table("medias").select("*").ilike("title", f"%{smart_pattern}%").execute()

    target_title = normalize_title(title)
    target_year  = str(year).strip() if year else None

    for row in res.data or []:
        row_title = normalize_title(row["title"])
        row_year  = str(row.get("year") or "").strip()

        title_match = row_title == target_title
        year_match  = (not target_year) or (row_year == target_year)

        if title_match and year_match:
            return row

    return None


def find_existing_media(tmdb_id: Optional[str], title: str, year: Optional[str]) -> Optional[dict]:
    """
    البوابة المركزية للبحث عن الميديا بترتيب الأولويات:
    TMDB ID → عنوان دقيق → بحث مرن.
    تُعيد الصف الكامل من DB أو None.
    """
    if tmdb_id:
        result = _find_media_by_tmdb_id(tmdb_id)
        if result:
            return result

    result = _find_media_by_exact_title(title, year)
    if result:
        return result

    return _find_media_by_smart_pattern(title, year)

def is_media_data_complete(tmdb_id: Optional[str], title: str, year: Optional[str]) -> dict:
    """
    التحقق مما إذا كان العمل موجوداً في قاعدة البيانات وبياناته (القصة والبوستر) مكتملة.
    يُستخدم لتخطي جلب البيانات من TMDB ورفع الصور إذا كانت موجودة مسبقاً.
    """
    media = find_existing_media(tmdb_id, title, year)
    if not media:
        return {"exists": False, "is_complete": False, "data": None}

    # التحقق من اكتمال البيانات الأساسية (القصة والبوستر)
    story = media.get("story")
    poster = media.get("poster_url")
    
    has_story = story and story not in _USELESS_VALUES
    has_poster = poster and poster not in _USELESS_VALUES and "via.placeholder.com" not in poster

    return {
        "exists": True,
        "is_complete": bool(has_story and has_poster),
        "data": media
    }
# ===========================================================================
# Section 3: Media Operations — عمليات جدول medias
# ===========================================================================

def _create_media(payload: dict) -> Optional[dict]:
    """إنشاء سجل ميديا جديد باستخدام upsert لمنع التكرار اللحظي."""
    res = supabase.table("medias").upsert(
        payload, on_conflict="normalized_title,year"
    ).execute()
    return res.data[0] if res.data else None


def _sync_media_slug(media_id: int, base_slug: str) -> str:
    """
    التأكد من أن الـ slug يبدأ بالـ ID للتوافق مع Next.js.
    يُحدّث DB لو الـ slug القديم مختلف ويُعيد الـ slug النهائي.
    """
    target_slug = f"{media_id}-{base_slug}"
    res = supabase.table("medias").select("slug").eq("id", media_id).execute()

    if not res.data:
        return target_slug

    current_slug = res.data[0]["slug"]
    if current_slug != target_slug:
        log.info(f"🔗 تحديث الـ Slug إلى: {target_slug}")
        supabase.table("medias").update({"slug": target_slug}).eq("id", media_id).execute()

    return target_slug


def upsert_media(
    tmdb_id: Optional[str],
    final_title: str,
    meta_story: str,
    final_poster: str,
    c_cat: str,
    meta_year: Optional[str],
    meta_rating: Optional[str],
    labels: Optional[str],
    runtime: Optional[str],
    duration_iso: Optional[str],
    base_slug: str,
) -> tuple[Optional[int], str, str, str]:
    """
    إيجاد أو إنشاء سجل الميديا وإعادة بياناته الأساسية.
    تُعيد: (media_id, final_slug, meta_story, final_poster).
    """
    m_type = "movie" if c_cat == "movie" else "series"

    media_payload = _clean_payload({
        "tmdb_id":      str(tmdb_id) if tmdb_id else None,
        "title":        final_title,
        "story":        meta_story,
        "poster_url":   final_poster,
        "category":     c_cat,
        "media_type":   m_type,
        "slug":         base_slug,
        "year":         str(meta_year) if meta_year else None,
        "rating":       str(meta_rating) if meta_rating else None,
        "labels":       labels,
        "runtime":      runtime,
        "duration_iso": duration_iso,
    })

    def _do_upsert():
        existing = find_existing_media(tmdb_id, final_title, meta_year)

        if existing:
            media_id = existing["id"]
            # نسحب البيانات الموجودة بدل ما ندهسها
            resolved_story  = existing.get("story")  or meta_story
            resolved_poster = existing.get("poster_url") or final_poster
            log.info(f"🛡️ [حماية]: تم العثور على '{final_title}' (ID: {media_id})، تم سحب البيانات دون تعديل.")
        else:
            log.info(f"🆕 [إنشاء]: سجل جديد لـ '{final_title}'...")
            new_row = _create_media(media_payload)
            media_id       = new_row["id"] if new_row else None
            resolved_story  = meta_story
            resolved_poster = final_poster

        return media_id, resolved_story, resolved_poster

    media_id, resolved_story, resolved_poster = _retry(_do_upsert, label="upsert_media")

    if not media_id:
        return None, base_slug, resolved_story, resolved_poster

    final_slug = _sync_media_slug(media_id, base_slug)
    return media_id, final_slug, resolved_story, resolved_poster


# ===========================================================================
# Section 4: Season Operations — عمليات جدول seasons
# ===========================================================================

def upsert_season(media_id: int, season_number: int) -> Optional[int]:
    """
    إيجاد أو إنشاء موسم وإعادة الـ ID.
    """
    log.info(f"📡 معالجة الموسم رقم {season_number} للميديا {media_id}...")

    try:
        existing = (
            supabase.table("seasons")
            .select("id")
            .eq("media_id", media_id)
            .eq("season_number", season_number)
            .execute()
        )

        if existing.data:
            s_id = existing.data[0]["id"]
            log.info(f"✅ الموسم موجود بالفعل (ID: {s_id})")
            return s_id

        log.info(f"🆕 إنشاء الموسم {season_number}...")
        new_season = supabase.table("seasons").insert({
            "media_id":      media_id,
            "season_number": season_number,
        }).execute()

        if new_season.data:
            s_id = new_season.data[0]["id"]
            log.info(f"✅ تم إنشاء الموسم (ID: {s_id})")
            return s_id

    except Exception as e:
        log.warning(f"⚠️ خطأ في معالجة الموسم: {e}")

    return None


# ===========================================================================
# Section 5: Episode Operations — عمليات جدول episodes
# ===========================================================================

def upsert_episode(
    media_id: int,
    season_id: Optional[int],
    episode_number: int,
    identifier: str,
    base_slug: str,
) -> Optional[int]:
    """
    إيجاد أو إنشاء حلقة، تحديث الـ identifier لو موجودة، وإعادة الـ ID.
    """
    ep_slug = f"{base_slug}-episode-{episode_number}"

    query = (
        supabase.table("episodes")
        .select("id")
        .eq("media_id", media_id)
        .eq("episode_number", episode_number)
    )

    if season_id is None:
        query = query.is_("season_id", "null")
    else:
        query = query.eq("season_id", season_id)

    existing = query.execute()

    if existing.data:
        e_id = existing.data[0]["id"]
        supabase.table("episodes").update({
            "identifier": identifier,
            "season_id":  season_id,
            "slug":       ep_slug,
        }).eq("id", e_id).execute()
        return e_id

    new_ep = supabase.table("episodes").insert({
        "media_id":       media_id,
        "season_id":      season_id,
        "episode_number": episode_number,
        "slug":           ep_slug,
        "identifier":     identifier,
        "status_message": "Waiting...",
        "progress_percent": 0,
    }).execute()

    return new_ep.data[0]["id"] if new_ep.data else None


# ===========================================================================
# Section 6: Genre Operations — عمليات جدول genres
# ===========================================================================

def _find_or_create_genre(genre_name: str) -> Optional[int]:
    """إيجاد أو إنشاء تصنيف وإعادة الـ ID."""
    genre_slug = genre_name.lower().replace(" ", "-")

    res = supabase.table("genres").select("id").eq("name", genre_name).execute()
    if res.data:
        return res.data[0]["id"]

    new_genre = supabase.table("genres").insert({
        "name": genre_name,
        "slug": genre_slug,
    }).execute()
    return new_genre.data[0]["id"] if new_genre.data else None


def _link_genre_to_media(media_id: int, genre_id: int) -> None:
    """ربط تصنيف بميديا في جدول media_genres."""
    supabase.table("media_genres").upsert(
        {"media_id": media_id, "genre_id": genre_id},
        on_conflict="media_id, genre_id",
    ).execute()


def sync_genres(media_id: int, labels: str) -> None:
    """
    مزامنة كل التصنيفات المرتبطة بميديا:
    تُنشئ أي تصنيف غير موجود وتربطه بالميديا.
    """
    genre_list = [g.strip() for g in labels.split(",") if g.strip()]
    for genre_name in genre_list:
        try:
            genre_id = _find_or_create_genre(genre_name)
            if genre_id:
                _link_genre_to_media(media_id, genre_id)
        except Exception as e:
            log.warning(f"⚠️ خطأ في معالجة التصنيف '{genre_name}': {e}")


# ===========================================================================
# Section 7: Links Operations — عمليات جدول links
# ===========================================================================

def _build_link_entries(
    episode_id: int,
    current_voe: Optional[str],
    current_vk: Optional[str],
    archive_url: Optional[str],
) -> list[dict]:
    """بناء قائمة الروابط الصالحة للحفظ."""
    entries = []
    invalid = {"Failed", "Pending", None, ""}

    if current_voe and current_voe not in invalid:
        entries.append({"episode_id": episode_id, "server_name": "voe", "url": current_voe})

    if current_vk and current_vk not in invalid:
        entries.append({"episode_id": episode_id, "server_name": "vk", "url": current_vk})

    if archive_url and archive_url not in invalid and "Failed" not in str(archive_url):
        entries.append({"episode_id": episode_id, "server_name": "archive", "url": archive_url})

    return entries


def save_links(
    episode_id: int,
    current_voe: Optional[str],
    current_vk: Optional[str],
    archive_url: Optional[str],
) -> None:
    """حفظ روابط التشغيل في جدول links مع retry لكل رابط."""
    if not episode_id:
        log.error("❌ فشل حفظ الروابط: episode_id غير موجود أو None")
        return

    entries = _build_link_entries(episode_id, current_voe, current_vk, archive_url)

    for entry in entries:
        def _do_upsert(e=entry):
            supabase.table("links").upsert(
                e, on_conflict="episode_id, server_name"
            ).execute()

        try:
            _retry(_do_upsert, label=f"link:{entry['server_name']}")
        except Exception as e:
            log.error(f"❌ فشل حفظ رابط {entry['server_name']} بعد {RETRY_COUNT} محاولات: {e}")


# ===========================================================================
# Section 8: Main Orchestrator — المنسق الرئيسي
# ===========================================================================

def save_to_supabase(
    current_voe: Optional[str],
    current_vk: Optional[str],
    display_title: str,
    original_task_name: str,
    meta_story: Optional[str],
    final_poster: Optional[str],
    meta_year: Optional[str],
    meta_rating: Optional[str],
    identifier: str,
    archive_url: Optional[str],
    meta_data: Optional[dict] = None,
    tmdb_id: Optional[str] = None,
    labels: Optional[str] = None,
    runtime: Optional[str] = None,
    duration_iso: Optional[str] = None,
    c_title: Optional[str] = None,
    c_cat: str = "movie",
    extracted_season_no: Optional[int] = None,
    actual_ep_no: Optional[int] = None,
    generated_slug: Optional[str] = None,
) -> Optional[tuple]:
    """
    المنسق الرئيسي لحفظ أي عمل في قاعدة البيانات.
    يتبع الترتيب: Media → Season → Episode → Genres → Links.
    يُعيد: (episode_id, media_id, meta_story, final_poster) أو None عند الفشل.
    """
    import traceback

    try:
        # ── 1. التحقق والإعداد ───────────────────────────────────────
        if not meta_year:
            log.warning("⚠️ meta_year مفقود قبل الحفظ.")

        if not c_title:
            log.warning(f"⚠️ c_title غير ممرر لـ '{display_title}'، سيُستخدم display_title.")
            c_title = display_title
            if c_cat != "tv":
                c_cat = "movie"

        final_title = _resolve_final_title(original_task_name, c_title)
        base_slug   = generated_slug or _build_slug(c_title)

        # ── 2. الميديا (Media) ───────────────────────────────────────
        media_id, final_slug, meta_story, final_poster = upsert_media(
            tmdb_id=tmdb_id, final_title=final_title,
            meta_story=meta_story, final_poster=final_poster,
            c_cat=c_cat, meta_year=meta_year, meta_rating=meta_rating,
            labels=labels, runtime=runtime, duration_iso=duration_iso,
            base_slug=base_slug,
        )

        if not media_id:
            log.error("❌ فشل إنشاء أو إيجاد الميديا. إيقاف الحفظ.")
            return None

        # ── 3. الموسم (Season) — للمسلسلات فقط ─────────────────────
        season_id = None
        if c_cat == "tv":
            season_number = extracted_season_no or 1
            season_id = upsert_season(media_id, season_number)

        # ── 4. الحلقة (Episode) ──────────────────────────────────────
        ep_number  = actual_ep_no or 1
        episode_id = upsert_episode(media_id, season_id, ep_number, identifier, final_slug)

        if not episode_id:
            log.error("❌ فشل إنشاء الحلقة.")
            return None

        # ── 5. التصنيفات (Genres) ────────────────────────────────────
        if labels and media_id:
            sync_genres(media_id, labels)

        # ── 6. الروابط (Links) ───────────────────────────────────────
        save_links(episode_id, current_voe, current_vk, archive_url)

        log.info(f"✅ تم الحفظ الكامل: media={media_id}, episode={episode_id}")
        return episode_id, media_id, meta_story, final_poster

    except Exception as e:
        log.error("🚨 Supabase Crash Traceback:")
        log.error(traceback.format_exc())
        log.error(f"❌ خطأ تفصيلي أثناء الحفظ: {str(e)}")
        return None


# ===========================================================================
# Section 9: Public Helpers — الدوال العامة المساعدة
# ===========================================================================

def initialize_supabase_record(
    display_title: str,
    original_task_name: str,
    tmdb_data: dict,
    temp_id: str,
) -> tuple:
    """
    إنشاء سجل أولي في Supabase (pending) لعمل لم ينتهِ تحميله بعد.
    تُعيد: (episode_id, media_id, meta_story, final_poster).
    """
    from downloader_new.metadata.formatter import get_clean_media_data
    clean = get_clean_media_data(original_task_name)
    init_cat    = clean[1] if clean and len(clean) == 4 else "movie"
    init_season = clean[2] if clean and len(clean) == 4 else None
    init_ep     = clean[3] if clean and len(clean) == 4 else None
    log.info(f"DEBUG init: original_task_name={original_task_name} | cat={init_cat} | season={init_season} | ep={init_ep}")

    save_res = save_to_supabase(
        current_voe=None,
        current_vk="Pending",
        display_title=display_title,
        original_task_name=original_task_name,
        c_cat=init_cat,
        extracted_season_no=init_season,
        actual_ep_no=init_ep,
        meta_story=tmdb_data.get("story"),
        final_poster=tmdb_data.get("poster"),
        meta_year=tmdb_data.get("year"),
        meta_rating=tmdb_data.get("rating"),
        identifier=temp_id,
        archive_url="Pending",
        tmdb_id=tmdb_data.get("tmdb_id"),
        labels=tmdb_data.get("labels"),
        runtime=tmdb_data.get("runtime"),
        duration_iso=tmdb_data.get("duration"),
    )

    if save_res and len(save_res) == 4:
        return save_res

    log.error("❌ فشل الحفظ الأولي في قاعدة البيانات.")
    return None, None, "", ""