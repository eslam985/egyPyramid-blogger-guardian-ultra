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


def get_movie_data(name):
    search_query = str(name).strip()
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
        movie_id = re.search(r"tt\d+", search_query).group()
    elif "themoviedb.org/movie/" in search_query:
        movie_id = re.search(r"/movie/(\d+)", search_query).group(1)
    elif search_query.startswith("tt"):
        movie_id = search_query
    elif search_query.startswith("tmdb"):
        movie_id = search_query.replace("tmdb", "")

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
        year_match = re.search(r"(\d{4})", search_query)
        year = year_match.group(1) if year_match else None

        # التعديل هنا: ننشئ متغير جديد للبحث (query_for_search)
        # ونترك clean_query كما هي (تساوي search_query) للحفاظ على السنة
        query_for_search = (
            re.sub(r"\d{4}", "", search_query)
            .replace(":", "")
            .replace("_", " ")
            .strip()
        )
        clean_query = (
            search_query  # نضمن أن الاسم الأصلي بالسنة هو اللي هيفضل مكمل معانا
        )

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
            search_url = f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_API_KEY}&query={query_for_search}&language=ar"
            if year:
                search_url += f"&year={year}"
            res = requests.get(search_url).json()
            if res.get("results"):
                first_res = res["results"][0]
                # دعم تاريخ الأفلام (release_date) وتاريخ المسلسلات (first_air_date)
                tmdb_date = (
                    first_res.get("release_date")
                    or first_res.get("first_air_date")
                    or "0000"
                )
                tmdb_year = tmdb_date[:4]
                if not year or tmdb_year == year:
                    tmdb_final_id = first_res["id"]
                    # تخزين نوع المحتوى عشان نطلبه صح (movie أو tv)
                    content_kind = first_res.get("media_type", "movie")

        # --- المرحلة الثانية: OMDb (لو TMDB فشل في السنة) ---
        # --- المرحلة الثانية: OMDb (لو TMDB فشل في السنة) ---
        if not tmdb_final_id and year:
            print(f"⚠️ TMDB فشل بالسنة.. جاري فحص OMDb بالاسم والسنة: {year}")
            # لضمان أن البحث في OMDb نظيف تماماً من أي رموز
            omdb_query = query_for_search.replace(" ", "+")
            omdb_url = (
                f"http://www.omdbapi.com/?apikey={OMDB_API_KEY}&t={omdb_query}&y={year}"
            )
            res_o = requests.get(omdb_url).json()

            if res_o.get("Response") == "True":
                omdb_title = res_o.get("Title", "").lower()
                # فلتر القناص: التأكد أن الكلمة الأولى من بحثك موجودة في عنوان OMDb
                search_first_word = clean_query.strip().split(" ")[0].lower()

                if search_first_word in omdb_title:
                    raw_story = res_o.get("Plot", "")
                    try:
                        story = (
                            translator.translate(raw_story)
                            if raw_story != "N/A"
                            else "لا يوجد وصف"
                        )
                    except:
                        story = raw_story

                    # --- التعديل هنا: رفع بوستر OMDb قبل الخروج ---
                    omdb_poster = res_o.get("Poster")
                    if omdb_poster and omdb_poster != "N/A":
                        print(f"☁️ جاري رفع بوستر OMDb لكلاود ناري...")
                        omdb_poster = upload_poster_to_cloudinary(omdb_poster)

                    return (
                        res_o.get("imdbID"),  # ID
                        res_o.get("Title"),  # Title
                        story,  # Story
                        omdb_poster,  # Poster المرفوع
                        "أفلام",  # Labels
                        "PT02H00M",  # Duration ISO
                        res_o.get("imdbRating"),  # Rating
                        res_o.get("Runtime"),  # Runtime String
                        res_o.get("Year"),  # Year
                    )
                else:
                    print(
                        f"🛑 رفض النتيجة: OMDb أعاد '{omdb_title}' وهي لا تطابق '{clean_query}'"
                    )

        # --- المرحلة الثالثة: الصرامة المطلقة (بديل البحث المرن والـ AI) ---
        if not tmdb_final_id:
            print(f"🛑 لم يتم العثور على تطابق رسمي لـ '{search_query}'.")

            # تنظيف ذكي جداً للاسم حتى لو فشل البحث تماماً
            display_name = search_query
            if "http" in str(search_query) or "/" in str(search_query):
                # استخراج آخر جزء من الرابط وتنظيفه
                display_name = str(search_query).split("/")[-1].split("?")[0]
                display_name = display_name.replace("-", " ").replace("_", " ").title()
                # حذف أي أرقام تعريفية في بداية الاسم (مثل 123-movie-name)
                display_name = re.sub(r"^\d+-", "", display_name).strip()

            # إذا ظل الاسم فارغاً لأي سبب، نضع الاسم الأصلي
            if not display_name:
                display_name = search_query

            return (
                None,
                display_name,
                None,  # خليه يرجع None عشان سوبابيز ما يمسحش القصة القديمة
                None,  # خليه يرجع None عشان ما يمسحش البوستر القديم
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

            # القاعدة: الأولوية للاسم العربي، لو مش موجود نأخذ الإنجليزي، لو مش موجود ننظف الرابط
            title = (
                ar_data.get("title")
                or ar_data.get("name")
                or en_data.get("title")
                or en_data.get("name")
            )

            if not title or "http" in str(title):
                title = search_query.split("/")[-1].replace("-", " ").title()
                title = re.sub(r"^\d+-", "", title).strip()

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
            runtime = en_data.get("runtime") or (
                en_data.get("episode_run_time", [0])[0]
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
    """رفع البوستر ومعالجته لكلاود ناري"""
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
            return f"https://res.cloudinary.com/{cloud_name}/image/upload/q_auto,f_auto,w_600,h_900,c_fill,g_auto/{public_id}.webp"
        return image_url
    except:
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

        print(f"DEBUG: VK Save API Response: {res_save}")

        if "response" in res_save:
            upload_url = res_save["response"]["upload_url"]
            video_id = res_save["response"]["video_id"]
            owner_id = res_save["response"]["owner_id"]

            file_size = os.path.getsize(file_path)
            pbar_vk = tqdm_custom(
                total=file_size,
                desc=f"📡 VK Upload: {title}",
                unit="B",
                unit_scale=True,
            )
            stream = ProgressStream(file_path, pbar_vk)

            # 2. الرفع المباشر مع تحديد نوع الملف
            # Using 'files' parameter for multipart-encoded file upload
            print(
                f"📡 جاري ضخ بايتات الفيديو لـ VK (المسار المحلي) - URL: {upload_url}..."
            )
            # requests will set the correct Content-Type for multipart/form-data automatically
            files = {"video_file": (os.path.basename(file_path), stream, "video/mp4")}
            # تعديل: إضافة Session لثبات الاتصال ومحاولة الرفع مع التعامل مع أخطاء SSL
            session = requests.Session()
            adapter = requests.adapters.HTTPAdapter(
                max_retries=3
            )  # محاولة الرفع 3 مرات في حال الفشل
            session.mount("https://", adapter)

            try:
                # أضفنا timeout معقول بدلاً من None لمنع التعليق اللانهائي
                # verify=True للتأكد من شهادة الأمان، وإذا استمر الخطأ جرب تحويلها لـ False (كحل أخير)
                response = session.post(
                    upload_url, files=files, timeout=600, verify=True
                )
            except requests.exceptions.SSLError:
                print("⚠️ فشل SSL، محاولة الرفع بدون تحقق (Insecure Mode)...")
                response = session.post(
                    upload_url, files=files, timeout=600, verify=False
                )

            pbar_vk.close()
            stream.close()

            print(f"DEBUG: VK File Upload Response Status: {response.status_code}")
            print(f"DEBUG: VK File Upload Response Text: {response.text}")

            if response.status_code == 200:
                print(
                    f"✅ VK Upload Success. Fetching Secure Embed Link (Retry Loop)..."
                )

                # محاولة جلب الرابط 3 مرات بفاصل 15 ثانية بين كل محاولة
                for attempt in range(40):
                    time.sleep(20)
                    get_api_url = "https://api.vk.com/method/video.get"
                    get_params = {
                        "videos": f"{owner_id}_{video_id}",
                        "access_token": VK_ACCESS_TOKEN,
                        "v": "5.131",
                    }

                    try:
                        res_get = requests.get(get_api_url, params=get_params).json()
                        if "response" in res_get and res_get["response"].get("items"):
                            video_data = res_get["response"]["items"][0]
                            embed_url = video_data.get("player")

                            if embed_url:
                                embed_url = embed_url.replace("vk.com", "vkvideo.ru")
                                connector = "&" if "?" in embed_url else "?"
                                embed_url += f"{connector}hd=2&autoplay=0"

                                print(f"✅ VK Embed Captured & Fixed: {embed_url}")
                                return embed_url

                        print(
                            f"⚠️ محاولة {attempt+1}: الفيديو قيد المعالجة، إعادة المحاولة..."
                        )
                    except Exception as e:
                        print(f"⚠️ خطأ في المحاولة {attempt+1}: {e}")

                # بناء رابط Embed يدوي في حال فشل الـ API في إرجاع player
                access_key = res_save["response"].get("access_key", "")
                fallback_url = f"https://vkvideo.ru/video_ext.php?oid={owner_id}&id={video_id}&hash={access_key}&hd=2"
                print(
                    f"⚠️ فشل استخراج Embed بعد 60 محاولات، تم بناء رابط احتياطي: {fallback_url}"
                )
                return fallback_url
            else:
                print(f"❌ فشل رفع ملف VK: Status {response.status_code}")
                return None
    except Exception as e:
        print(f"⚠️ فشل VK المحلي: {e}")
        return None


async def upload_to_voe_api(file_path, identifier):
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:  # أضف هذا السطر هنا
            file_name = os.path.basename(file_path).replace(" ", "%20")
            remote_url = f"https://archive.org/download/{identifier}/{file_name}"
            params = {"key": VOE_API_KEY, "url": remote_url}

            # 1. طلب الرفع
            response = await client.get(
                "https://voe.sx/api/upload/url", params=params, timeout=30
            )
            res = response.json()
            if res.get("status") != 200:
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
        "myvidplay.com",
        "doodstream.com",
    ]
    clean_file_name = urllib.parse.quote(file_name)
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
                if data.get("msg") == "OK":
                    print(f"✅ DoodStream: تم قبول الأمر عبر {domain}")
                    break
            except Exception:
                continue

        if not data or data.get("msg") != "OK":
            return None

        # التعديل وفقاً للتوثيق: المفتاح هو filecode والنتيجة قاموس
        f_code = data.get("result", {}).get("filecode")
        print(f"🔍 DoodStream Task ID: {f_code}")

        # محاولات الفحص (نزيد الوقت قليلاً لضمان عدم الحظر)
        for i in range(1, 31):
            await asyncio.sleep(20)  # 15 ثانية وقت مثالي للملفات الصغيرة
            print(f"🔄 DoodStream Polling Attempt {i}/30...")

            for domain in api_domains:
                try:
                    # الطريقة الأضمن: اسأل عن "معلومات الملف" مباشرة بالـ f_code
                    info_url = f"https://{domain}/api/file/info?key={api_key}&file_code={f_code}"
                    res = await client.get(info_url)
                    info_data = res.json()

                    # إذا رد السيرفر بمعلومات الملف وكان الـ status 200 (أي الملف موجود)
                    if info_data.get("status") == 200:
                        result = info_data.get("result", [{}])[0]
                        # التأكد أن الملف ليس "ممسوحاً" أو "قيد المعالجة الصعبة"
                        if result.get("file_code") == f_code:
                            print(f"✅ DoodStream Success (Found via File Info)!")
                            return f"https://myvidplay.com/e/{f_code}"

                    # إذا فشل Info، جرب الـ Status التقليدي
                    try:
                        # استخدام Check بدلاً من Info لسرعة الرد
                        check_url = f"https://{domain}/api/file/check?key={api_key}&file_code={f_code}"
                        res = await client.get(check_url)
                        check_data = res.json()

                        if check_data.get("status") == 200:
                            # التوثيق يقول النتيجة قائمة والوضع Active
                            results = check_data.get("result", [])
                            if results and results[0].get("status") == "Active":
                                print(f"✅ DoodStream Success (File is Active)!")
                                return f"https://myvidplay.com/e/{f_code}"
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
                            return f"https://myvidplay.com/e/{f.get('file_code')}"
                except:
                    pass
        return None


async def upload_to_streamtape(login, key, identifier, file_name):
    """الرفع لـ Streamtape مع قنص الرابط بالاسم"""
    print(f"📡 Streamtape: إرسال أمر سحب من الأرشيف...")
    try:
        clean_file_name = urllib.parse.quote(file_name)
        remote_url = f"https://archive.org/download/{identifier}/{clean_file_name}"

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            add_url = f"https://api.streamtape.com/remotedl/add?login={login}&key={key}&url={remote_url}"
            res = await client.get(add_url)
            data = res.json()

            # التأكد من قبول السيرفر للأمر
            # التأكد من قبول السيرفر للأمر
            if data.get("status") == 200:
                remote_id = data.get("result", {}).get("id")

                # تعريف دالة التنظيف داخل السياق لمرة واحدة
                def clean_it(text):
                    return "".join(e for e in text.lower() if e.isalnum())

                target = clean_it(file_name.split(".")[0])

                for i in range(1, 31):
                    await asyncio.sleep(20)
                    print(f"🔄 Streamtape Polling Attempt {i}/30...")

                    # 1. الفحص المباشر عبر الـ ID (الأولوية القصوى حسب الديكومنتيشن)
                    try:
                        status_url = f"https://api.streamtape.com/remotedl/status?login={login}&key={key}&id={remote_id}"
                        s_res = await client.get(status_url)
                        s_data = s_res.json()
                        task_info = s_data.get("result", {}).get(remote_id, {})

                        # إذا ظهر الرابط في حقل url يعني المهمة اكتملت
                        # التعديل هنا: سحب الـ id الفعلي للملف من نتيجة الفحص
                        if task_info.get("url"):
                            print(f"✅ Streamtape Success (Direct Match)!")
                            final_id = task_info.get("id")  # هذا هو المعرف الأضمن للملف
                            return f"https://streamtape.com/e/{final_id}"
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
        clean_file_name = urllib.parse.quote(file_name)
        remote_url = f"https://archive.org/download/{identifier}/{clean_file_name}"
        base_api = "https://lulustream.com/api"

        # زيادة التايم أوت للرفع لمنع التكرار (عشان ميفكرش إنه فشل ويعيد)
        async with httpx.AsyncClient(timeout=100.0, follow_redirects=True) as client:
            add_url = f"{base_api}/upload/url?key={key}&url={urllib.parse.quote(remote_url, safe='')}"
            res = await client.get(add_url)
            data = res.json()

            if data.get("status") == 200 and "result" in data:
                file_code = data["result"].get("filecode")
                print(f"✅ تم قبول الرفع! الكود: {file_code}")

                async def hunter_fixer(target_code, target_title):
                    print(f"🕵️ [Hunter] بدأت عملية 'القناص' للملف {target_code}...")

                    for attempt in range(1, 21):
                        print(f"🔄 [Hunter] محاولة رقم {attempt}...")
                        try:
                            async with httpx.AsyncClient(timeout=30.0) as hunter_client:
                                # 1. الطريقة الأولى: الهجوم المباشر (Direct Edit)
                                # إحنا معانا الكود، ليه نستنى القائمة؟ نعدل فوراً!
                                edit_params = {
                                    "key": key,
                                    "file_code": target_code,
                                    "file_title": target_title,
                                }
                                edit_res = await hunter_client.get(
                                    f"{base_api}/file/edit", params=edit_params
                                )

                                # لو السيرفر قبل التعديل، يبقى المهمة انتهت بنجاح
                                if "true" in edit_res.text or (
                                    edit_res.text.strip().startswith("{")
                                    and edit_res.json().get("status") == 200
                                ):
                                    print(
                                        f"✨ [Hunter] نجاح اختراق! تم تثبيت الاسم بالهجوم المباشر: {target_title}"
                                    )
                                    return

                                # 2. الطريقة الثانية: البحث العميق (لو المباشر فشل)
                                list_url = f"{base_api}/file/list?key={key}&per_page=100"  # فحص 100 ملف!
                                list_res = await hunter_client.get(list_url)

                                if list_res.status_code == 200:
                                    files = (
                                        list_res.json()
                                        .get("result", {})
                                        .get("files", [])
                                    )

                                    # البحث بـ 3 طرق: الكود، أو الاسم المشوه، أو تطابق جزئي
                                    for f in files:
                                        is_match = (f["file_code"] == target_code) or (
                                            "D8" in f["title"] and attempt < 5
                                        )  # لو لسه برفع وملقتش الكود، خد أي حد مشوه

                                        if is_match:
                                            f_code = f["file_code"]
                                            print(
                                                f"🎯 [Hunter] تم اصطياد الملف في القائمة (كود: {f_code}). جاري التعديل..."
                                            )
                                            await hunter_client.get(
                                                f"{base_api}/file/edit",
                                                params={
                                                    "key": key,
                                                    "file_code": f_code,
                                                    "file_title": target_title,
                                                },
                                            )
                                            print(f"✨ [Hunter] تم التصحيح بنجاح!")
                                            return

                                print(
                                    f"😴 [Hunter] لم يعثر عليه بعد.. السيرفر لم يدرج الملف في القائمة."
                                )

                        except Exception as e:
                            print(f"⚠️ [Hunter] خطأ فني في المحاولة: {e}")

                        await asyncio.sleep(60)  # انتظر دقيقة بين كل محاولة
                    print(f"🛑 [Hunter] فشلت في العثور على الملف بعد 20 محاولة.")

                # شغل القناص فوراً
                asyncio.create_task(hunter_fixer(file_code, file_name))
                return f"https://lulustream.com/e/{file_code}"

    except Exception as e:
        print(f"❌ LuluStream Fatal Error: {e}")
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


def get_clean_media_data(raw_name):
    # 1. البحث عن النمط الأجنبي (S01E05) أو العربي المختصر (ح 5)
    # أضفنا [ح] للبحث عن حرف ح يليه رقم
    pattern = re.search(r"(?:[sS](\d+)[eE]|[ح]\s*)(\d+)", raw_name)

    # 2. البحث عن النمط العربي الطويل (الحلقة 5)
    arabic_pattern = re.search(r"(?:الحلقة|حلقة)\s*(\d+)", raw_name)

    if pattern:
        category = "tv"
        ep_no = int(pattern.group(2))
        # تنظيف الاسم من النمط المكتشف
        clean_title = re.sub(r"(?:[sS]\d+[eE]|[ح]\s*)\d+.*", "", raw_name).strip()
    elif arabic_pattern or any(word in raw_name for word in ["مسلسل", "موسم"]):
        category = "tv"
        ep_no = int(arabic_pattern.group(1)) if arabic_pattern else 1
        clean_title = re.sub(
            r"[-–]?\s*(?:الحلقة|حلقة|الموسم|موسم)\s*\d+.*", "", raw_name
        ).strip()
    else:
        category = "movie"
        ep_no = 1
        clean_title = raw_name.strip()

    return clean_title, category, ep_no


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
