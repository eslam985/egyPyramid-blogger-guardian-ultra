import os
import time
import re
from supabase import create_client, Client as SupabaseClient

# 1. استيراد اللوجر
try:
    from .logger_setup import get_beast_logger
except ImportError:
    from logger_setup import get_beast_logger

log = get_beast_logger("GuardianUltra")

# 2. إعدادات قاعدة البيانات
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    log.error("❌ خطأ: لم يتم العثور على مفاتيح Supabase في متغيرات البيئة!")

supabase: SupabaseClient = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- دالتك اللي أنت نقلتها بتبدأ من هنا ---


    
    # كمل باقي كود الدالة بتاعك هنا...
def save_to_supabase(
    current_voe,
    current_down,
    current_vk,
    display_title,
    original_task_name,
    meta_story,
    final_poster,  # أضفهم هنا كمعاملات عادية
    meta_year,
    meta_rating,
    identifier,
    archive_url,
    meta_data=None,
    tmdb_id=None,
    labels=None,
    runtime=None,
    duration_iso=None,
):
    # استيراد الدوال دي "جوه" الدالة عشان نهرب من مشكلة الـ Circular Import
    try:
        from .processors import get_clean_media_data, normalize_title
    except ImportError:
        from processors import get_clean_media_data, normalize_title

        # نستخدم الاسم النظيف لاستخراج العنوان والنوع ورقم الموسم والحلقة
        c_title, c_cat, extracted_season_no, actual_ep_no = get_clean_media_data(
            display_title
        )

        # توليد slug تلقائي للميديا
        # إذا كان الاسم إنجليزي، نستخدم الحروف الإنجليزية، وإذا كان عربي نستخدم العربي
        generated_slug = c_title.lower().strip().replace(" ", "-")
        # تنظيف الـ slug من الرموز الغريبة مع الحفاظ على الحروف العربية والإنجليزية والأرقام والشرطة
        generated_slug = re.sub(r"[^a-z0-9\u0600-\u06FF-]", "", generated_slug)
        # إزالة الشرطات المتكررة
        generated_slug = re.sub(r"-+", "-", generated_slug).strip("-")

        # --- [تعديل 1]: تحديد الميديا تايب بدقة (movie / series) ---
        # الـ category بتفضل movie/tv عشان السيستم القديم، بس الـ media_type بيبقى موفي/سيريس
        m_type = "movie" if c_cat == "movie" else "series"

        # --- [تعديل 2]: حماية التايتل (لو التاسك فيه اسم يدوي نستخدمه) ---
        # بنشيك هل original_task_name رابط؟ لو مش رابط يبقى هو الأولوية
        if original_task_name and not original_task_name.startswith(
            ("http://", "https://")
        ):
            final_title = original_task_name
        else:
            final_title = c_title  # الاسم اللي السكربت نظفه أو جابه من TMDB

        media_payload = {
            "tmdb_id": str(tmdb_id) if tmdb_id else None,
            "title": final_title,  # العنوان المحمي
            "story": meta_story,
            "poster_url": final_poster,
            "category": c_cat,  # movie or tv (للسيستم)
            "media_type": m_type,  # movie or series (للموقع)
            "slug": generated_slug,
            "year": str(meta_year),
            "rating": str(meta_rating),
            "labels": labels,
            "runtime": runtime,
            "duration_iso": duration_iso,
        }
        # تنظيف ذكي: يحذف القيمة لو كانت None أو نص بيدل على الفشل أو رابط Placeholder
        useless_values = [
            None,
            "",
            "لا يوجد وصف",
            "جاري تحديث القصة...",
            "N/A",
            "غير محدد",
        ]

        media_payload = {
            k: v
            for k, v in media_payload.items()
            if v not in useless_values and "via.placeholder.com" not in str(v)
        }
        # 1. ابحث عن المسلسل أولاً لمنع دهس البيانات (القصة والبوستر)
        # --- بداية الجزء المحصن ضد أخطاء 502 ---
        m_id = None
        e_id = None
        for attempt in range(3):
            try:
                # 1. البحث عن أو إنشاء الميديا (Media)
                existing_media = (
                    supabase.table("medias")
                    .select("id")
                    .eq("title", c_title)
                    .eq("year", str(meta_year))
                    .execute()
                )

                # --- التعديل النهائي والذكي جداً بعد تفعيل Unique في سوبابيز ---
                # 1. البحث عن الميديا (بالـ ID أولاً ثم بالاسم المنظف) لضمان عدم التكرار
                m_id = None
                query = None

                # محاولة البحث بالـ ID لو متوفر
                if tmdb_id:
                    query = (
                        supabase.table("medias")
                        .select("*")
                        .eq("tmdb_id", str(tmdb_id))
                        .execute()
                    )

                # لو مفيش ID أو منفعش، نبحث بالاسم الذكي
                if not query or not query.data:
                    # الخطوة 1: البحث المطابق المباشر
                    query = (
                        supabase.table("medias")
                        .select("*")
                        .eq("title", c_title)
                        .eq("year", str(meta_year))
                        .execute()
                    )

                    # الخطوة 2: لو لسه مش موجود، نجرب البحث بـ "like" للكلمات الأساسية
                    if not query.data:
                        # نجلب كل الأعمال اللي فيها جزء من الاسم ونفلترها برمجياً
                        # ده حل "ذكي" للأعمال العربية اللي مش في TMDB
                        search_results = (
                            supabase.table("medias")
                            .select("*")
                            .ilike("title", f"%{c_title}%")
                            .execute()
                        )
                        for row in search_results.data:
                            if normalize_title(row["title"]) == c_title:
                                query = search_results
                                query.data = [row]  # نكتفي بهذا السجل
                                break

                if query and query.data:
                    m_id = query.data[0]["id"]

                    # --- التعديل: قراءة البيانات "لحساب" المتغيرات وليس للتعديل ---
                    # بنسحب القصة والبوستر من سوبابيز عشان نستخدمهم في تليجرام صح
                    existing_data = query.data[0]

                    if existing_data.get("story"):
                        meta_story = existing_data["story"]
                    if existing_data.get("poster_url"):
                        final_poster = existing_data["poster_url"]

                    log.info(
                        f"🛡️ [حماية]: تم العثور على '{c_title}' (ID: {m_id})، تم سحب البيانات للأرشفة دون تعديل."
                    )
                else:
                    # استخدام upsert لضمان أنه في حالة "السباق اللحظي" لا يحدث خطأ 23505
                    log.info(f"🆕 [إنشاء]: سجل جديد لـ '{c_title}'...")
                    new_media = (
                        supabase.table("medias")
                        .upsert(media_payload, on_conflict="title, year")
                        .execute()
                    )
                    if new_media.data:
                        m_id = new_media.data[0]["id"]

                # --- [تعديل جوهري]: تحديث الـ slug ليبدأ بـ ID الميديا لضمان توافق Next.js ---
                if m_id:
                    # نستخدم الـ generated_slug الأصلي ونضيف له الـ ID
                    # نتأكد أولاً أن الـ slug الحالي لا يبدأ بالفعل بالـ ID الصحيح
                    check_res = (
                        supabase.table("medias").select("slug").eq("id", m_id).execute()
                    )
                    if check_res.data:
                        current_db_slug = check_res.data[0]["slug"]
                        target_slug = f"{m_id}-{generated_slug}"

                        if current_db_slug != target_slug:
                            log.info(f"🔗 تحديث الرابط (Slug) إلى: {target_slug}")
                            supabase.table("medias").update({"slug": target_slug}).eq(
                                "id", m_id
                            ).execute()
                            generated_slug = target_slug
                        else:
                            generated_slug = current_db_slug

                break  # إذا وصلنا هنا بنجاح، نخرج من حلقة المحاولات
            except Exception as e:
                if attempt < 2:
                    log.warning(
                        f"⚠️ سوبابيز متعثر في مرحلة التعريف (502)، محاولة {attempt+1}..."
                    )
                    time.sleep(3)
                else:
                    raise e  # لو فشل تماماً بعد 3 مرات يرمي الخطأ للـ Except الكبيرة
        # --- نهاية الجزء المحصن ---

        # --- [تعديل جوهري]: إنشاء أو تحديث الموسم (Season) أولاً للمسلسلات ---
        s_id = None
        if c_cat == "tv":
            # استخدام رقم الموسم المستخرج بدلاً من الهاردكود
            season_number = extracted_season_no if extracted_season_no else 1
            season_slug = f"{generated_slug}-season-{season_number}"
            log.info(f"📡 جاري معالجة الموسم رقم {season_number} للميديا {m_id}...")
            try:
                # البحث عن الموسم أو إنشاؤه
                existing_season = (
                    supabase.table("seasons")
                    .select("id")
                    .eq("media_id", m_id)
                    .eq("season_number", season_number)
                    .execute()
                )
                if existing_season.data:
                    s_id = existing_season.data[0]["id"]
                    log.info(f"✅ تم العثور على الموسم في القاعدة بـ ID: {s_id}")
                else:
                    log.info(f"🆕 الموسم {season_number} غير موجود، جاري إنشاؤه...")
                    new_season = (
                        supabase.table("seasons")
                        .insert(
                            {
                                "media_id": m_id,
                                "season_number": season_number,
                                "slug": season_slug,
                            }
                        )
                        .execute()
                    )
                    if new_season.data:
                        s_id = new_season.data[0]["id"]
                        log.info(f"✅ تم إنشاء موسم جديد بـ ID: {s_id}")
            except Exception as se:
                log.warning(f"⚠️ خطأ في إنشاء الموسم: {se}")

        # --- [تعديل جوهري]: إنشاء أو تحديث الحلقة (Episode) قبل الروابط ---
        actual_ep_no = actual_ep_no if actual_ep_no else 1
        ep_slug = f"{generated_slug}-episode-{actual_ep_no}"

        episode_payload = {
            "media_id": m_id,
            "season_id": s_id,  # ربط الحلقة بالموسم
            "episode_number": actual_ep_no,
            "slug": ep_slug,  # إضافة slug للحلقة
            "identifier": identifier,
            "status_message": "Waiting...",
            "progress_percent": 0,
        }

        # البحث عن الحلقة لإنشائها أو تحديث الـ identifier الخاص بها
        existing_ep = (
            supabase.table("episodes")
            .select("id")
            .eq("media_id", m_id)
            .eq("episode_number", actual_ep_no)
            .execute()
        )

        if existing_ep.data:
            e_id = existing_ep.data[0]["id"]
            supabase.table("episodes").update(
                {"identifier": identifier, "season_id": s_id, "slug": ep_slug}
            ).eq("id", e_id).execute()
        else:
            new_ep = supabase.table("episodes").insert(episode_payload).execute()
            if new_ep.data:
                e_id = new_ep.data[0]["id"]

        # --- [تعديل]: التعامل مع التصنيفات (Genres) تلقائياً ---
        if labels and m_id:
            genre_list = [g.strip() for g in labels.split(",") if g.strip()]
            for g_name in genre_list:
                try:
                    g_slug = g_name.lower().replace(" ", "-")
                    # 1. البحث عن التصنيف أو إنشاؤه
                    genre_res = (
                        supabase.table("genres")
                        .select("id")
                        .eq("name", g_name)
                        .execute()
                    )
                    g_id = None
                    if genre_res.data:
                        g_id = genre_res.data[0]["id"]
                    else:
                        new_g = (
                            supabase.table("genres")
                            .insert({"name": g_name, "slug": g_slug})
                            .execute()
                        )
                        if new_g.data:
                            g_id = new_g.data[0]["id"]

                    # 2. ربط التصنيف بالميديا في جدول media_genres
                    if g_id:
                        supabase.table("media_genres").upsert(
                            {"media_id": m_id, "genre_id": g_id},
                            on_conflict="media_id, genre_id",
                        ).execute()
                except Exception as ge:
                    log.warning(f"⚠️ خطأ في معالجة التصنيف {g_name}: {ge}")

        # 1. بناء القائمة الآن بعد التأكد من وجود e_id
        link_entries = []
        if e_id:  # تأكد أن الـ ID موجود
            if current_voe and current_voe not in ["Failed", "Pending"]:
                link_entries.append(
                    {"episode_id": e_id, "server_name": "voe", "url": current_voe}
                )
            if current_vk and current_vk not in ["Failed", "Pending"]:
                link_entries.append(
                    {"episode_id": e_id, "server_name": "vk", "url": current_vk}
                )
            if archive_url and "Failed" not in archive_url and archive_url != "Pending":
                link_entries.append(
                    {"episode_id": e_id, "server_name": "archive", "url": archive_url}
                )
            if current_down and current_down != "Failed":
                link_entries.append(
                    {"episode_id": e_id, "server_name": "download", "url": current_down}
                )

        # 2. الآن نقوم بتحديث السيرفرات الموجودة فقط (تنفيذ الـ upsert لكل رابط في القائمة)
        # 2. الآن نقوم بتحديث السيرفرات الموجودة فقط مع آلية إعادة المحاولة (Retry)
        for entry in link_entries:
            for attempt in range(3):  # حاول 3 مرات كحد أقصى
                try:
                    supabase.table("links").upsert(
                        entry, on_conflict="episode_id, server_name"
                    ).execute()
                    break  # نجح الأمر، اخرج من حلقة المحاولات لهذا الرابط
                except Exception as link_err:
                    if attempt < 2:
                        log.warning(
                            f"⚠️ سوبابيز مشغول (502/Timeout)، محاولة رقم {attempt+1} خلال 3 ثوانٍ..."
                        )
                        time.sleep(3)
                    else:
                        log.error(
                            f"❌ فشل تسجيل رابط {entry['server_name']} بعد 3 محاولات: {link_err}"
                        )
        return e_id, m_id, meta_story, final_poster
    except Exception as e:
        log.error(f"❌ خطأ أثناء الحفظ في ساب باز: {e}")
        return None, None, meta_story, final_poster