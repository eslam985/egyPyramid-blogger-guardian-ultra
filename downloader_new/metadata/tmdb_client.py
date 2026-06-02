# /media/es/DDrive/projects/apps-python/egyPyramid-guardian-ultra/downloader_new/metadata/tmdb_client.py
import requests
import re
import os
from deep_translator import GoogleTranslator

from downloader_new.shared.logger import get_beast_logger
from downloader_new.metadata.images import upload_poster_to_cloudinary
from downloader_new.shared.helpers import minutes_to_iso, is_mostly_english

log = get_beast_logger("GuardianUltra")
translator = GoogleTranslator(source="auto", target="ar")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
OMDB_API_KEY = os.getenv("OMDB_API_KEY")

genre_map = {
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


def get_movie_data(name, year=None):  # <--- أضفنا year هنا
    search_query = str(name).strip()
    original_input = search_query

    # كشف لو المدخل رابط أو ID
    is_url_or_id = "http" in search_query or search_query.startswith(("tt", "tmdb"))

    if "dramaboxdb.com" in search_query:
        print("⚡ DramaBox detected: Skipping browser simulation (Direct Fallback)...")
        # استخراج الاسم من الرابط مباشرة
        fallback_title = search_query.split("/")[-1].replace("-", " ").title()
        return (
            None,  # ID
            fallback_title,
            "وصف تلقائي (DramaBox Archive)",
            "https://via.placeholder.com/600x900?text=Egy+Pyramid",
            "DramaBox",
            "PT01H00M",
            "8.5",
            "N/A",
            "N/A",
        )
    movie_id = None

    # استخراج ID من رابط IMDb أو TMDB أو كتابة يدوية
    if "imdb.com/title/" in search_query:
        id_match = re.search(r"(tt\d+)", search_query)
        if id_match:
            movie_id = id_match.group(1)
    elif "themoviedb.org/movie/" in search_query:
        id_match = re.search(r"/movie/(\d+)", search_query)
        if id_match:
            movie_id = id_match.group(1)
            content_kind = "movie"
    elif "themoviedb.org/tv/" in search_query:
        id_match = re.search(r"/tv/(\d+)", search_query)
        if id_match:
            movie_id = id_match.group(1)
            content_kind = "tv"
    elif "omdbapi.com" in search_query:
        id_match = re.search(r"[iI]=(tt\d+)", search_query)
        if id_match:
            movie_id = id_match.group(1)
    elif search_query.startswith("tt"):
        movie_id = search_query
    elif search_query.startswith("tmdb-tv-"):
        movie_id = search_query.replace("tmdb-tv-", "")
        content_kind = "tv"
    elif search_query.startswith("tmdb-"):
        movie_id = search_query.replace("tmdb-", "")
        content_kind = "movie"
    elif search_query.startswith("tmdb"):
        movie_id = re.sub(r"[^0-9]", "", search_query)

    # القيم الافتراضية
    title, story, poster, labels, duration = (
        search_query,
        "لا يوجد وصف",
        "",
        "أفلام",
        "PT02H00M",
    )
    rating, runtime_str, release_year = "N/A", "غير محدد", "غير محدد"

    try:
        # 1. استخراج السنة والاسم (فصل السنة للبحث فقط دون حذفها من الأصل)
        # إذا كان المدخل رابطاً، نتجنب استخراج السنة منه لأنه قد يحتوي على IDs طويلة تخدع الـ Regex
        # استخراج السنة والاسم
        if is_url_or_id:
            extracted_year = None
            query_for_search = search_query
        else:
            # المحاولة الأولى: لو في سنة مبعوتة للدالة من بره نستخدمها
            if year:
                extracted_year = str(year)
            else:
                # المحاولة الثانية: لو مفيش، نستخرجها من الاسم بالـ Regex
                year_match = re.search(r"(\d{4})", search_query)
                extracted_year = year_match.group(1) if year_match else None

            # تنظيف الكويري من أي سنين عشان البحث في TMDB يكون دقيق بالاسم فقط
            query_for_search = (
                re.sub(r"\d{4}", "", search_query)
                .replace(":", "")
                .replace("_", " ")
                .strip()
            )

        # الآن نعتمد السنة النهائية للبحث
        final_year = extracted_year

        clean_query = search_query

        # --- المرحلة الأولى: TMDB (بحث بالـ ID أو الاسم) ---
        tmdb_final_id = None

        # إذا كان معنا ID جاهز (رقمي أو tt)
        if movie_id:
            if str(movie_id).startswith("tt"):
                find_url = f"https://api.themoviedb.org/3/find/{movie_id}?api_key={TMDB_API_KEY}&external_source=imdb_id&language=ar"
                res_f = requests.get(find_url).json()
                # التحقق من الأفلام أو المسلسلات
                if res_f.get("movie_results"):
                    tmdb_final_id = res_f["movie_results"][0]["id"]
                    content_kind = "movie"  # تأكيد النوع
                elif res_f.get("tv_results"):
                    tmdb_final_id = res_f["tv_results"][0]["id"]
                    content_kind = "tv"  # تأكيد النوع
            else:
                tmdb_final_id = movie_id

        # إذا لم يتوفر ID، نبحث بالاسم والسنة كالعادة
        if not tmdb_final_id:
            # نستخدم query_for_search هنا عشان محرك البحث ميتلخبطش بالسنة
            # الجديد: تحديد المسار بناءً على الكلمة المفتاحية في العنوان
            if any(
                word in original_input
                for word in [
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
                ]
            ):
                search_path = "tv"
                content_kind = "tv"
            else:
                search_path = "movie"
                content_kind = "movie"

            search_url = f"https://api.themoviedb.org/3/search/{search_path}?api_key={TMDB_API_KEY}&query={query_for_search}&language=ar"
            if final_year:  # <--- تأكد إنها بتستخدم السنة المختارة
                search_url += f"&year={final_year}"
            res = requests.get(search_url).json()
            if res.get("results"):
                # --- التعديل المنقذ: التأكد من تطابق الاسم لتجنب نتائج الأفلام العشوائية ---
                best_match = None
                for r in res["results"]:
                    res_title = (r.get("name") or r.get("title") or "").lower()
                    # لو الاسم اللي راجع فيه كلمة من اللي باحثين عنها، نعتبره هو الصح
                    if (
                        query_for_search.lower() in res_title
                        or res_title in query_for_search.lower()
                    ):
                        best_match = r
                        break

                if best_match:
                    first_res = best_match
                    tmdb_date = (
                        first_res.get("release_date")
                        or first_res.get("first_air_date")
                        or "0000"
                    )
                    tmdb_year = tmdb_date[:4]

                    if not year or tmdb_year == year:
                        tmdb_final_id = first_res["id"]
                        # أهم سطر: نجبد نوع المحتوى بناءً على البحث (tv أو movie) وليس ما يقترحه TMDB
                        content_kind = search_path
                else:
                    print(
                        f"⚠️ TMDB أعاد نتائج غير مطابقة للاسم: {query_for_search}. سيتم الانتقال للمرحلة الثالثة."
                    )

        # --- المرحلة الثانية: OMDb (لو TMDB فشل في السنة) ---
        # --- المرحلة الثانية: OMDb (لو TMDB فشل في السنة) ---
        # --- المرحلة الثانية: OMDb (لو TMDB فشل في السنة) ---
        if not tmdb_final_id and final_year:
            print(f"⚠️ TMDB فشل بالسنة.. جاري فحص OMDb بالاسم والسنة: {final_year}")

            # 1. السطر الناقص: تنفيذ طلب البحث في OMDb
            omdb_query = query_for_search.replace(" ", "+")
            omdb_url = f"http://www.omdbapi.com/?apikey={OMDB_API_KEY}&t={omdb_query}&y={final_year}"

            try:
                res_o = requests.get(omdb_url).json()  # هنا تم تعريف res_o

                if res_o.get("Response") == "True":
                    omdb_title = res_o.get("Title", "").lower()
                    search_first_word = query_for_search.strip().split(" ")[0].lower()

                    if search_first_word in omdb_title:
                        # 1. جلب القصة (Story)
                        raw_story = res_o.get("Plot", "")
                        try:
                            story = (
                                translator.translate(raw_story)
                                if raw_story != "N/A"
                                else "لا يوجد وصف"
                            )
                        except:
                            story = raw_story

                        # 2. جلب التصنيفات (Genres) - مترجمة لتجنب مشاكل الـ Duplicate Key
                        raw_genres = res_o.get("Genre", "أفلام").split(", ")
                        # نستخدم القاموس للترجمة، وإذا لم يوجد نأخذ الكلمة كما هي
                        translated_list = [
                            genre_map.get(g.strip(), g.strip()) for g in raw_genres
                        ]
                        labels = ", ".join(translated_list)

                        # 3. جلب مدة العمل (Runtime) - من IMDb
                        raw_runtime = res_o.get("Runtime", "N/A")
                        runtime_str = "غير محدد"
                        duration = "PT01H30M"

                        if raw_runtime != "N/A":
                            runtime_str = raw_runtime
                            minutes_match = re.search(r"(\d+)", raw_runtime)
                            if minutes_match:
                                m = int(minutes_match.group(1))
                                duration = f"PT{m//60:02d}H{m%60:02d}M"
                                hours = m // 60
                                mins = m % 60
                                runtime_str = (
                                    f"{hours} ساعة و {mins} دقيقة"
                                    if hours > 0
                                    else f"{m} دقيقة"
                                )

                        # 4. جلب التقييم وسنة العرض - ضمان تحويل التقييم لنص رقمي
                        raw_rating = res_o.get("imdbRating", "0")
                        rating = str(raw_rating) if raw_rating != "N/A" else "0.0"
                        release_year = res_o.get("Year", final_year or "N/A")

                        # 5. معالجة البوستر
                        omdb_poster = res_o.get("Poster")
                        if omdb_poster and omdb_poster != "N/A":
                            print(f"☁️ جاري رفع بوستر IMDb (عبر OMDb) لكلاود ناري...")
                            omdb_poster = upload_poster_to_cloudinary(omdb_poster)

                        return (
                            res_o.get("imdbID"),  # ID
                            res_o.get("Title"),  # Title
                            story,  # Story (المترجمة)
                            omdb_poster,  # Poster المرفوع
                            labels,  # التصنيفات (المترجمة عربي)
                            duration,  # ISO Duration
                            rating,  # التقييم (الذي أصلحناه)
                            runtime_str,  # الوقت المقروء
                            release_year,  # السنة
                        )
                    else:
                        print(
                            f"🛑 رفض النتيجة: OMDb أعاد '{omdb_title}' وهي لا تطابق '{query_for_search}'"
                        )

            except Exception as e:
                print(f"⚠️ خطأ أثناء الاتصال بـ OMDb: {e}")

        # --- المرحلة الثالثة: الصرامة المطلقة (بديل البحث المرن والـ AI) ---
        # --- المرحلة الثالثة: الصرامة المطلقة ---
        if not tmdb_final_id:
            print(f"🛑 لم يتم العثور على تطابق رسمي لـ '{search_query}'.")

            # لو المدخل اسم يدوي مش رابط، خده زي ما هو فوراً
            if not is_url_or_id:
                display_name = original_input
            else:
                # لو رابط، نظفه وطلع منه اسم
                display_name = str(search_query).split("/")[-1].split("?")[0]
                display_name = display_name.replace("-", " ").replace("_", " ").title()
                display_name = re.sub(r"^\d+-", "", display_name).strip()

            # التأمين الأخير
            if not display_name:
                display_name = original_input

            return (
                None,
                display_name,
                None,
                None,
                "أفلام",
                "PT01H30M",
                "N/A",
                "غير محدد",
                final_year or "غير محدد",
            )

        if tmdb_final_id:
            # استخدام النوع المستخرج (movie أو tv) لطلب البيانات بشكل صحيح
            media_type = content_kind if "content_kind" in locals() else "movie"

            # 1. جلب البيانات بالإنجليزي (للحصول على الاسم الرسمي الأصلي)
            en_url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_final_id}?api_key={TMDB_API_KEY}"
            en_data = requests.get(en_url).json()

            # --- التعديل الجوهري هنا ---
            # جلب البيانات بالعربي (لأننا نفضل الاسم العربي في تليجرام وسوبابيز)
            ar_url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_final_id}?api_key={TMDB_API_KEY}&language=ar"
            ar_data = requests.get(ar_url).json()

            # القاعدة الذكية: لو المدخل إنجليزي أو رابط، نفضل الاسم الإنجليزي من TMDB
            # لو المدخل عربي صريح، نفضل الاسم العربي
            if is_mostly_english(original_input) or is_url_or_id:
                title = (
                    en_data.get("title")
                    or en_data.get("name")
                    or ar_data.get("title")
                    or ar_data.get("name")
                )
            else:
                title = (
                    ar_data.get("title")
                    or ar_data.get("name")
                    or en_data.get("title")
                    or en_data.get("name")
                )

            if not title or "http" in str(title):
                # إذا فشل كل شيء، نحاول استخراج الاسم من الرابط الأصلي
                title = (
                    original_input.split("/")[-1]
                    .replace("-", " ")
                    .replace("_", " ")
                    .title()
                )
                # حذف أي أرقام تعريفية في بداية الاسم (مثل 123-movie-name)
                title = re.sub(r"^\d+-", "", title).strip()
                # حذف الـ query parameters لو موجودة
                title = title.split("?")[0]

            print(f"✅ تم العثور على الاسم الرسمي: {title}")
            # --------------------------

            # استكمال باقي البيانات (تاريخ، تقييم، بوستر)
            tmdb_date = (
                en_data.get("release_date") or en_data.get("first_air_date") or "0000"
            )
            release_year = tmdb_date[:4]
            # ... باقي الكود كما هو ...

            raw_rating = en_data.get("vote_average", 0.0)
            rating = str(round(raw_rating, 1)) if raw_rating > 0 else "N/A"
            poster = (
                f"https://image.tmdb.org/t/p/original{en_data.get('poster_path')}"
                if en_data.get("poster_path")
                else poster
            )

            # مدة الحلقة أو الفيلم
            # مدة الحلقة أو الفيلم
            runtime = en_data.get("runtime") or (
                en_data.get("episode_run_time")[0]
                if en_data.get("episode_run_time")
                else None
            )
            if runtime:
                # تحديث الـ ISO Format بناءً على الدقائق الحقيقية
                duration = minutes_to_iso(runtime)
                runtime_str = (
                    f"{runtime // 60} ساعة و {runtime % 60} دقيقة"
                    if runtime >= 60
                    else f"{runtime} دقيقة"
                )
            else:
                duration = "PT01H30M"  # قيمة افتراضية لو مفيش runtime

            # 2. جلب البيانات بالعربي
            ar_url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_final_id}?api_key={TMDB_API_KEY}&language=ar"
            ar_data = requests.get(ar_url).json()

            # منطق القصة الذكي
            story = ar_data.get("overview")
            if not story or story.strip() == "":
                raw_en_story = en_data.get("overview")
                if raw_en_story:
                    try:
                        story = translator.translate(raw_en_story)
                    except:
                        story = raw_en_story
                else:
                    story = "لا يوجد وصف"

            # جلب التصنيفات بالعربي
            genres = ar_data.get("genres", [])
            if genres:
                labels = ", ".join([g["name"] for g in genres])

        # --- المرحلة النهائية: رفع البوستر لكلاود ناري قبل العودة بالنتائج ---
        # --- المرحلة النهائية: تخص TMDB فقط (لأن OMDb خرج بـ return خاص به أعلاه) ---
        print(f"☁️ جاري معالجة بوستر TMDB ورفعه لكلاود ناري...")
        final_poster = upload_poster_to_cloudinary(poster)

        return (
            tmdb_final_id,
            title,
            story,
            final_poster,  # الرابط المرفوع (Cloudinary)
            labels,
            duration,
            rating,
            runtime_str,
            release_year,
        )

    except Exception as e:
        print(f"⚠️ خطأ في الخوارزمية المزدوجة: {e}")
        return (
            tmdb_final_id,
            title,
            story,
            poster,
            labels,
            duration,
            rating,
            runtime_str,
            release_year,
        )


def check_local_radar(query, year):
    """فحص الفهرس المحلي لجلب الـ ID قبل البحث الخارجي"""
    try:
        from downloader_new.metadata.local_lookup import search_local_imdb

        return search_local_imdb(query, year)
    except Exception as e:
        log.error(f"❌ خطأ في الرادار المحلي: {e}")
        return None


def fetch_tmdb_metadata(search_query: str, year=None) -> dict:
    """
    جلب بيانات الميديا من TMDB/IMDB.
    تعيد قاموساً بالمفاتيح: tmdb_id, display_title, story, poster, labels,
    duration, rating, runtime, year.
    في حالة فشل أو نقص البيانات، تعيد قيماً افتراضية.
    """
    log.info(f"🔍 جلب بيانات العمل من TMDB/IMDB للتحقق من الأرشيف...")
    log.info(f"🔎 البحث عن: {search_query} " + (f"({year})" if year else "") + " ...")
    log.info(f"DEBUG: calling get_movie_data with {search_query}")

    # --- التعديل هنا: محاولة جلب الـ ID محلياً أولاً ---
    local_id = check_local_radar(search_query, year)
    if local_id:
        log.info(f"✨ تم العثور على ID محلي: {local_id}. سيتم استخدامه مباشرة.")
        # نرسل الـ ID بدلاً من اسم البحث لضمان الدقة
        movie_result = get_movie_data(local_id, year=year)
    else:
        # المسار القديم في حال لم يجد شيئاً محلياً
        movie_result = get_movie_data(search_query, year=year)
    # --- نهاية التعديل ---
    log.info(f"DEBUG: get_movie_data returned: {movie_result}")

    if isinstance(movie_result, (list, tuple)) and len(movie_result) >= 9:
        (
            tmdb_id_fetched,
            display_title_tmdb,
            meta_story,
            final_poster,
            meta_labels,
            meta_duration,
            meta_rating,
            meta_runtime,
            meta_year,
        ) = movie_result[:9]
    else:
        log.warning(
            f"⚠️ بيانات TMDB ناقصة أو غير صالحة لـ {search_query}، سيتم استخدام الافتراضي."
        )
        tmdb_id_fetched, display_title_tmdb, meta_story, final_poster = (
            None,
            search_query,
            "",
            "",
        )
        meta_labels, meta_duration, meta_rating, meta_runtime, meta_year = (
            [],
            "",
            "0",
            0,
            year or "N/A",
        )

    return {
        "tmdb_id": tmdb_id_fetched,
        "display_title": display_title_tmdb,
        "story": meta_story,
        "poster": final_poster,
        "labels": meta_labels,
        "duration": meta_duration,
        "rating": meta_rating,
        "runtime": meta_runtime,
        "year": meta_year,
    }
