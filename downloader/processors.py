import os
import re
import json
import time
import asyncio
import httpx
import urllib.parse
import requests
from google import genai
from deep_translator import GoogleTranslator
from functools import partial
from .engine import ProgressStream
import traceback

try:
    from .logger_setup import get_beast_logger
except ImportError:
    import sys
    import os
log = get_beast_logger("GuardianUltra")
# 1. استيراد القاعدة الأساسية أولاً
try:
    from tqdm.auto import tqdm as tqdm_base
except ImportError:
    import tqdm as tqdm_base

# 2. التعريف (خارج بلوك الـ try/except) لضمان توفره في كل الحالات
tqdm_custom = partial(
    tqdm_base, dynamic_ncols=False, mininterval=2.0, ascii=" #", ncols=80
)

# 3. توحيد الاسم عالمياً لخدمة أي مكتبات خارجية ولإصلاح أخطاء Ruff
tqdm = tqdm_custom


# سحب المفاتيح من متغيرات البيئة (التي وضعتها في Secrets)
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
OMDB_API_KEY = os.getenv("OMDB_API_KEY")
VOE_API_KEY = os.getenv("VOE_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
VK_ACCESS_TOKEN = os.getenv("VK_ACCESS_TOKEN")
VK_GROUP_ID = os.getenv("VK_GROUP_ID")
VK_ALBUM_ID = os.getenv("VK_ALBUM_ID", "2")  # "2" كقيمة افتراضية إذا لم يوجد سكرت

# بناء القاموس من متغيرات البيئة
CLOUDINARY_CONFIG = {
    "cloud_name": os.getenv("CLOUDINARY_CLOUD_NAME"),
    "upload_preset": os.getenv("CLOUDINARY_UPLOAD_PRESET"),
}

translator = GoogleTranslator(source="auto", target="ar")
client = genai.Client(api_key=GEMINI_API_KEY)


def minutes_to_iso(minutes):
    if not minutes or not isinstance(minutes, int):
        return "PT01H30M"
    hours = minutes // 60
    mins = minutes % 60
    return f"PT{hours:02d}H{mins:02d}M"


def is_mostly_english(text):
    if not text:
        return True
    # إزالة الرموز والأرقام
    clean_text = re.sub(r"[^a-zA-Z\u0600-\u06FF]", "", str(text))
    if not clean_text:
        return True
    english_chars = len(re.findall(r"[a-zA-Z]", clean_text))
    arabic_chars = len(re.findall(r"[\u0600-\u06FF]", clean_text))
    return english_chars >= arabic_chars


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
            "2026",
            "2026",
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
                if res_f.get("movie_results"):
                    tmdb_final_id = res_f["movie_results"][0]["id"]
            else:
                tmdb_final_id = movie_id  # إذا كان رقم TMDB مباشر

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
                        release_year = res_o.get("Year", final_year or "2026")

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
                year or "2026",
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


def upload_poster_to_cloudinary(image_url):
    """رفع البوستر ومعالجته لكلاود ناري بترميز WebP المتوافق مع تليجرام وبلوجر"""
    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME")
    upload_preset = os.getenv("CLOUDINARY_UPLOAD_PRESET")

    if not cloud_name or not upload_preset:
        return image_url

    try:
        cloudinary_api = f"https://api.cloudinary.com/v1_1/{cloud_name}/image/upload"
        payload = {
            "file": image_url,
            "upload_preset": upload_preset,
            "folder": "blogger",
        }
        res = requests.post(cloudinary_api, data=payload).json()
        public_id = res.get("public_id")

        if public_id:
            # f_webp: تجعل كلاود ناري يسلم الصورة بصيغة WebP مهما كان الأصل
            # q_auto:good: تعطي جودة ممتازة مع حجم صغير جداً
            transform = "c_fill,g_auto,w_300,h_450,q_auto:good,f_avif"

            return f"https://res.cloudinary.com/{cloud_name}/image/upload/{transform}/v1/{public_id}.avif"

        return image_url
    except Exception as e:
        print(f"⚠️ خطأ في رفع الصورة لكلاود ناري: {e}")
        return image_url


def upload_to_vk_local(title, file_path):
    try:
        if not os.path.exists(file_path):
            print(f"⚠️ ملف VK غير موجود: {file_path}")
            return None

        # 1. حجز المكان
        api_url = "https://api.vk.com/method/video.save"
        params = {
            "name": title,
            "group_id": VK_GROUP_ID,
            "access_token": VK_ACCESS_TOKEN,
            "v": "5.131",
        }
        res_save = requests.get(api_url, params=params).json()

        if "response" not in res_save:
            print(
                f"❌ فشل حجز مكان في VK: {res_save.get('error', {}).get('error_msg')}"
            )
            return None

        upload_url = res_save["response"]["upload_url"]
        video_id = res_save["response"]["video_id"]
        owner_id = res_save["response"]["owner_id"]

        # --- [ مرحلة الضخ السريع ] ---
        print(f"📡 جاري ضخ الفيديو لـ VK بنظام Stream (المسار المحلي)...")
        try:
            with open(file_path, "rb") as f:
                files = {"video_file": (os.path.basename(file_path), f, "video/mp4")}
                response = requests.post(upload_url, files=files, timeout=600)

            if response.status_code != 200:
                print(f"❌ فشل ضخ الملف لـ VK: Status {response.status_code}")
                return None
            print("   ✅ انتهى الضخ بنجاح. يبدأ الآن فحص المعالجة وقنص الرابط...")
        except Exception as e:
            print(f"   ❌ خطأ أثناء الضخ المحلي: {str(e)}")
            return None

        # --- [ مرحلة القنص الذكي - Polling ] ---
        for check_attempt in range(1, 31):
            time.sleep(30)
            get_url = "https://api.vk.com/method/video.get"
            get_params = {
                "videos": f"{owner_id}_{video_id}",
                "access_token": VK_ACCESS_TOKEN,
                "v": "5.131",
            }
            try:
                res_get = requests.get(get_url, params=get_params).json()
                if "response" in res_get and res_get["response"].get("items"):
                    video_data = res_get["response"]["items"][0]
                    embed_url = video_data.get("player")
                    if embed_url:
                        final_url = embed_url.replace("vk.com", "vkvideo.ru")
                        connector = "&" if "?" in final_url else "?"
                        final_url += f"{connector}hd=2&autoplay=0"
                        print(f"✅ تم القنص بنجاح لـ VK! | الرابط: {final_url}")
                        return final_url
                print(f"⏳ VK يعالج الفيديو حالياً ({check_attempt}/30)...")
            except Exception as e:
                print(f"⚠️ خطأ في فحص المعالجة: {e}")

        # --- [ الحل الاحتياطي الأخير لو الفحص فشل بعد 15 دقيقة ] ---
        access_key = res_save["response"].get("access_key", "")
        fallback_url = f"https://vkvideo.ru/video_ext.php?oid={owner_id}&id={video_id}&hash={access_key}&hd=2"
        print(f"⚠️ فشل استخراج Embed تلقائياً، تم بناء رابط احتياطي: {fallback_url}")
        return fallback_url

    except Exception as e:
        print(f"⚠️ فشل VK المحلي: {e}")
        return None


async def upload_to_voe_api(file_path, identifier):
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:  # أضف هذا السطر هنا

            file_name = os.path.basename(file_path).replace(" ", "%20")
            if str(identifier).startswith("http"):
                remote_url = identifier
            else:
                remote_url = f"https://archive.org/download/{identifier}/{file_name}"
            params = {"key": VOE_API_KEY, "url": remote_url}

            # 1. طلب الرفع مع محاولات إعادة في حال تذبذب الرابط
            res = {}
            for attempt in range(3):
                try:
                    response = await client.get(
                        "https://voe.sx/api/upload/url", params=params, timeout=30
                    )
                    res = response.json()
                    if res.get("status") == 200:
                        break
                except Exception as e:
                    log.warning(f"⚠️ Voe: فشل اتصال في المحاولة {attempt+1}: {e}")
                
                await asyncio.sleep(5)

            if res.get("status") != 200:
                log.error(f"❌ Voe: فشل الرفع نهائياً: {res}")
                return None

            file_code = res.get("result", {}).get("file_code")

            print(f"⏳ جاري متابعة حالة الرفع على Voe...")
            start_time = time.time()

            # تعريف شريط واحد فقط بتنسيق كامل ونظيف
            # ... قبل الحلقة ...
            check_count = 0
            pbar_voe = tqdm_custom(total=100, desc="⏳ Voe Polling")

            while time.time() - start_time < 800:
                try:
                    status_response = await client.get(
                        f"https://voe.sx/api/file/status?key={VOE_API_KEY}&file_code={file_code}"
                    )
                    status_res = status_response.json()
                    status = status_res.get("result", {}).get("status")

                    check_count += 1

                    if status == "finished":
                        pbar_voe.update(100 - pbar_voe.n)
                        pbar_voe.set_description("✅ Voe: Finished!")
                        pbar_voe.close()
                        return file_code

                    # المحاكاة الذكية: لو بيحمل حرك الشريط لغاية 40% ولو بيعالج حركه لغاية 80%
                    # المحاكاة الذكية: تعيين القيمة مباشرة بدلاً من update التراكمي في بعض الأحيان
                    if status == "downloading":
                        pbar_voe.n = min(40, pbar_voe.n + 5)
                    elif status == "processing":
                        pbar_voe.n = min(80, pbar_voe.n + 5)

                    pbar_voe.refresh()  # مهم جداً لرؤية الحركة فوراً

                    pbar_voe.set_description(
                        f"⏳ Voe Status: {status if status else 'Queued'}"
                    )
                    pbar_voe.refresh()

                    # صمام الأمان: لو السيرفر استهبل أكتر من دقيقتين والملف اترفع فعلاً
                    if check_count >= 5:
                        pbar_voe.set_description(
                            "⚠️ Voe Slow Response - Proceeding to VK..."
                        )
                        pbar_voe.close()
                        return file_code

                except:
                    pass

                await asyncio.sleep(25)

            pbar_voe.close()
            return file_code
    except Exception as e:
        print(f"⚠️ خطأ Voe API: {e}")
        return None


async def upload_to_doodstream(api_key, identifier, file_name):
    """الرفع لـ DoodStream مع تجربة نطاقات متعددة وفحص صبور"""
    print(f"📡 DoodStream: إرسال أمر سحب من الأرشيف...")

    # قائمة النطاقات البديلة للـ API
    api_domains = [
        "doodapi.co",
        "d_api.com",
        "doodapi.com",
        "dood.to",
        "dood.stream",
        "playmogo.com",
        "doodstream.com",
    ]
    clean_file_name = urllib.parse.quote(file_name)
    if str(identifier).startswith("http"):
        remote_url = identifier
    else:
        remote_url = f"https://archive.org/download/{identifier}/{clean_file_name}"

    headers = {"User-Agent": "Mozilla/5.0"}

    async with httpx.AsyncClient(
        timeout=30.0, headers=headers, follow_redirects=True
    ) as client:
        # محاولة إرسال الأمر باستخدام النطاقات المتاحة
        data = None
        for domain in api_domains:
            try:
                # نقوم بعمل encode للاسم لضمان وصوله للسيرفر بالحروف العربية
                safe_title = urllib.parse.quote(file_name)
                add_url = f"https://{domain}/api/upload/url?key={api_key}&url={remote_url}&new_title={safe_title}"
                response = await client.get(add_url)
                data = response.json()
                # بدلاً من الشرط الحالي، خليه أشمل:
                if data.get("msg") == "OK" or data.get("success") is True:
                    print(f"✅ DoodStream: تم قبول الأمر عبر {domain}")
                    break
            except Exception:
                await asyncio.sleep(2) # انتظار بسيط قبل تجربة نطاق آخر
                continue

        if not data or (data.get("msg") != "OK" and not data.get("success")):
            return None

        # التعديل وفقاً للتوثيق: المفتاح هو filecode والنتيجة قاموس
        f_code = data.get("result", {}).get("filecode")
        print(f"🔍 DoodStream Task ID: {f_code}")

        # محاولات الفحص (نزيد الوقت قليلاً لضمان عدم الحظر)
        for i in range(1, 21):
            await asyncio.sleep(20)  # 15 ثانية وقت مثالي للملفات الصغيرة
            print(f"🔄 DoodStream Polling Attempt {i}/20...")

            for domain in api_domains:
                try:
                    # الطريقة الأضمن: اسأل عن "معلومات الملف" مباشرة بالـ f_code
                    info_url = f"https://{domain}/api/file/info?key={api_key}&file_code={f_code}"
                    res = await client.get(info_url)
                    info_data = res.json()

                    # إذا رد السيرفر بمعلومات الملف وكان الـ status 200 (أي الملف موجود)
                    if info_data.get("status") == 200:
                        result = info_data.get("result", [{}])[0]
                        # بمجرد وجود الـ file_code والحجم (حتى لو لسه 0 أو بيزيد) نعتبره نجاح
                        if result.get("file_code") == f_code:
                            raw_size = result.get("size", 0)
                            size_mb = float(raw_size) / (1024 * 1024)
                            print(
                                f"✅ DoodStream Success: الملف موجود وبدأ المعالجة ({size_mb:.2f} MB)"
                            )
                            return f"https://playmogo.com/e/{f_code}"

                    # إذا فشل Info، جرب الـ Status التقليدي
                    try:
                        # استخدام Check بدلاً من Info لسرعة الرد
                        check_url = f"https://{domain}/api/file/check?key={api_key}&file_code={f_code}"
                        res = await client.get(check_url)
                        check_data = res.json()

                        if check_data.get("status") == 200:
                            results = check_data.get("result", [])
                            if results:  # أي نتيجة ترجع للملف ده يعني السيرفر شافه
                                print(f"✅ DoodStream Success (File Found in Check)!")
                                return f"https://playmogo.com/e/{f_code}"
                    except:
                        continue

                except Exception as e:
                    # لا تطبع كل الأخطاء لعدم ملء اللوجات، فقط لو كان الخطأ غريباً
                    continue

            # فحص أخير بالاسم في كل محاولة "زوجية" لتقليل الضغط
            if i % 2 == 0:
                try:
                    list_url = (
                        f"https://doodapi.co/api/file/list?key={api_key}&per_page=5"
                    )
                    l_res = await client.get(list_url)
                    files = l_res.json().get("result", {}).get("files", [])
                    # داخل دالة دود ستريم (جزء البحث بالاسم)
                    # البحث بالاسم العربي كما هو مسجل في السيرفر
                    search_term = file_name.split(".")[0].strip()
                    for f in files:
                        server_title = f.get("title", "")
                        if search_term in server_title:
                            print(
                                f"✅ DoodStream Found by Precise Arabic Name Match: {server_title}"
                            )
                            return f"https://playmogo.com/e/{f.get('file_code')}"
                except:
                    pass
        return None


async def upload_to_streamtape(login, key, identifier, file_name):
    """الرفع لـ Streamtape مع قنص الرابط بالاسم"""
    print(f"📡 Streamtape: إرسال أمر سحب من الأرشيف...")
    try:
        clean_file_name = urllib.parse.quote(file_name)
        if str(identifier).startswith("http"):
            remote_url = identifier
        else:
            remote_url = f"https://archive.org/download/{identifier}/{clean_file_name}"

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            # نقوم بعمل quote للاسم لضمان وصول الحروف العربية للسيرفر بشكل سليم
            safe_name = urllib.parse.quote(file_name)
            add_url = f"https://api.streamtape.com/remotedl/add?login={login}&key={key}&url={remote_url}&name={safe_name}"
            # محاولة قنص الرابط مع إعادة المحاولة في حال تذبذب البوت
            data = {}  # تعريف أولي فارغ
            for attempt in range(3):
                try:
                    res = await client.get(add_url)
                    data = res.json()
                    if data.get("status") == 200:
                        break
                except Exception as e:
                    log.warning(f"⚠️ خطأ في الاتصال: {e}")

                log.warning(f"⚠️ محاولة فاشلة ({attempt+1}/3)...")
                await asyncio.sleep(5)

            # التأكد من قبول السيرفر للأمر
            # التأكد من قبول السيرفر للأمر
            if data.get("status") == 200:
                remote_id = data.get("result", {}).get("id")

                # تعريف دالة التنظيف داخل السياق لمرة واحدة
                def clean_it(text):
                    return "".join(e for e in text.lower() if e.isalnum())

                target = clean_it(file_name.split(".")[0])

                for i in range(1, 21):
                    await asyncio.sleep(20)
                    print(f"🔄 Streamtape Polling Attempt {i}/20...")

                    # 1. الفحص المباشر عبر الـ ID (الأولوية القصوى حسب الديكومنتيشن)
                    try:
                        status_url = f"https://api.streamtape.com/remotedl/status?login={login}&key={key}&id={remote_id}"
                        s_res = await client.get(status_url)
                        s_data = s_res.json()
                        task_info = s_data.get("result", {}).get(remote_id, {})

                        # إذا ظهر الرابط في حقل url يعني المهمة اكتملت
                        # التعديل هنا: سحب الـ id الفعلي للملف من نتيجة الفحص
                        # التعديل: قنص المعرف الحقيقي (extid) بدلاً من معرف المهمة (id)
                        # 1. القنص الذكي للمعرف (من extid أو من الـ url مباشرة)
                        file_code = task_info.get("extid") or task_info.get("fileid")

                        if not file_code and task_info.get("url"):
                            try:
                                # استخراج المعرف من الرابط في حالة عدم وجود extid
                                file_code = (
                                    task_info.get("url").split("/v/")[1].split("/")[0]
                                )
                            except:
                                pass

                        # 2. إذا تم العثور على المعرف، المهمة اكتملت
                        if file_code:
                            # تثبيت الاسم لضمان الاحترافية
                            try:
                                rename_url = f"https://api.streamtape.com/file/rename?login={login}&key={key}&file={file_code}&name={urllib.parse.quote(file_name)}"
                                await client.get(rename_url)
                            except:
                                pass

                            print(f"✅ Streamtape Success! File ID: {file_code}")
                            return f"https://streamtape.com/e/{file_code}"
                    except Exception:
                        pass

                    # 2. نظام الطوارئ: فحص المجلد (في حال تأخر تحديث حالة الـ ID)
                    # 2. نظام الطوارئ المتطور: فحص المجلد بالكلمات المفتاحية
                    try:
                        list_url = f"https://api.streamtape.com/file/listfolder?login={login}&key={key}"
                        l_res = await client.get(list_url)
                        files = l_res.json().get("result", {}).get("files", [])

                        # استخراج الكلمات الهامة فقط من الاسم (مثل: المداح، 11)
                        keywords = [
                            k
                            for k in file_name.split(".")[0].replace("-", " ").split()
                            if len(k) > 1
                        ]

                        for f in files:
                            remote_name = f.get("name", "").lower()
                            # التحقق إذا كانت كل الكلمات المفتاحية موجودة في اسم الملف بالسيرفر
                            if all(
                                clean_it(k) in clean_it(remote_name) for k in keywords
                            ):
                                print(
                                    f"✅ Streamtape Success (Advanced Emergency Match)!"
                                )
                                return f"https://streamtape.com/e/{f.get('linkid')}"
                    except Exception:
                        pass

    except Exception as e:
        print(f"❌ Streamtape Global Error: {e}")

    return None


async def upload_to_lulustream(key, identifier, file_name):
    print(f"📡 LuluStream: بدء الرفع للملف: {file_name}")
    try:
        # التعديل هنا: إضافة www لتجنب خطأ الـ 301
        base_api = "https://www.lulustream.com/api"
        clean_file_name = urllib.parse.quote(file_name)
        if str(identifier).startswith("http"):
            remote_url = identifier
        else:
            remote_url = f"https://archive.org/download/{identifier}/{clean_file_name}"

        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            add_url = f"{base_api}/upload/url?key={key}&url={urllib.parse.quote(remote_url, safe='')}"

            data = {}
            for attempt in range(3):
                try:
                    res = await client.get(add_url)
                    if res.status_code == 200:
                        data = res.json()
                        if data.get("status") == 200:
                            break
                    log.warning(
                        f"⚠️ LuluStream: محاولة فاشلة ({attempt+1}/3).. الرمز: {res.status_code}"
                    )
                except Exception as e:
                    log.warning(f"⚠️ LuluStream: خطأ اتصال: {e}")

                await asyncio.sleep(5)

            if data.get("status") != 200:
                print(f"❌ LuluStream: فشل الطلب نهائياً بعد المحاولات: {data}")
                return None

            file_code = data["result"].get("filecode")
            print(f"✅ تم قبول الرفع! الكود: {file_code}")

            async def hunter_fixer(target_code, target_title):
                print(f"🕵️ [Hunter] بدأ مراقبة الكود: {target_code}")
                for attempt in range(1, 21):
                    try:
                        async with httpx.AsyncClient(timeout=30.0) as hunter_client:
                            # الاستعلام المباشر باستخدام النطاق المحدث
                            info_url = f"{base_api}/file/info?key={key}&file_code={target_code}"
                            info_res = await hunter_client.get(info_url)

                            if info_res.status_code == 200:
                                info_data = info_res.json()
                                if info_data.get("status") == 200 and info_data.get(
                                    "result"
                                ):
                                    file_info = info_data["result"][0]
                                    if file_info.get("canplay") == 1:
                                        print(
                                            f"🎯 [Hunter] الملف جاهز! جاري فرض الاسم النظيف..."
                                        )
                                        edit_params = {
                                            "key": key,
                                            "file_code": target_code,
                                            "file_title": target_title,
                                        }
                                        edit_res = await hunter_client.get(
                                            f"{base_api}/file/edit", params=edit_params
                                        )
                                        if "true" in edit_res.text:
                                            print(
                                                f"✨ [Hunter] نجاح: تم تثبيت الاسم: {target_title}"
                                            )
                                            return
                                    else:
                                        print(
                                            f"⏳ [Hunter] المحاولة {attempt}: الملف جاري معالجته..."
                                        )
                    except Exception as e:
                        print(f"⚠️ [Hunter] خطأ: {e}")
                    await asyncio.sleep(45)
                print(f"🛑 [Hunter] انتهت المحاولات.")

            asyncio.create_task(hunter_fixer(file_code, file_name))
            return f"https://lulustream.com/e/{file_code}"
    except Exception as e:
        print(f"❌ Fatal Error: {e}")
    return None


async def upload_to_mixdrop(file_path, email, key):
    print(f"💧 جاري الرفع إلى MixDrop...")
    try:
        async with httpx.AsyncClient(timeout=600.0, follow_redirects=True) as client:
            # البيانات المطلوبة حسب التوثيق
            data = {"email": email, "key": key}
            # إرسال الملف فعلياً
            with open(file_path, "rb") as f:
                files = {"file": f}
                response = await client.post(
                    "https://ul.mixdrop.ag/api", data=data, files=files
                )

                res_json = response.json()
                if res_json.get("success"):
                    # الرابط المطلوب للمشاهدة هو embedurl
                    embed_url = res_json["result"]["embedurl"]
                    # تأكد أن الرابط يبدأ بـ https
                    if not embed_url.startswith("https:"):
                        embed_url = "https:" + embed_url
                    print(f"✅ تم الرفع لـ MixDrop: {embed_url}")
                    return embed_url
                else:
                    print(f"❌ فشل MixDrop: {res_json}")
                    return None
    except Exception as e:
        print(f"⚠️ خطأ تقني في MixDrop: {e}")
        return None


def normalize_title(title):
    if not title:
        return ""

    t = str(title).lower()

    # --- الخطوة الناقصة والضرورية ---
    # حذف أي سنة (19xx أو 20xx) قبل أي عملية تنظيف تانية
    t = re.sub(r"\b(19|20)\d{2}\b", " ", t)
    # --------------------------------

    # تنظيف الرموز (الأرقام اللي هتفضل هنا هي أرقام الأجزاء فقط مثل John Wick 4)
    t = re.sub(r"[^a-zA-Z0-9\u0600-\u06FF\s]", " ", t)

    stop_words = [
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
    elif any(
        word in raw_name
        for word in [
            "مسلسل",
            "موسم",
            "الموسم",
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
        category = "tv"
        clean_title = raw_name

    # تنظيف العنوان النهائي باستخدام دالة normalize_title
    clean_title = normalize_title(clean_title)

    return clean_title, category, season_no, ep_no


def get_metadata_via_ai(name, year):
    print(f"🤖 جاري استدعاء الذكاء الاصطناعي للبحث والتدقيق (Gemini Search)...")
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
        print(f"❌ فشل الـ AI أيضاً: {e}")
        return None
