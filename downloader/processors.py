import requests
import asyncio
import google.generativeai as genai
from deep_translator import GoogleTranslator
import os
import re
import json
import time
from .engine import ProgressStream
import httpx  # أو استخدم requests
import tqdm
# إجبار tqdm على الثبات في سطر واحد
from functools import partial
tqdm.tqdm = partial(tqdm.tqdm, dynamic_ncols=False, mininterval=2.0, ascii=" #", force_cols=80)
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
genai.configure(api_key=GEMINI_API_KEY)


def get_movie_data(name):
    search_query = str(name).strip()
    if "dramaboxdb.com" in search_query:
        print("⚡ DramaBox detected: Skipping browser simulation (Direct Fallback)...")
        # استخراج الاسم من الرابط مباشرة
        fallback_title = search_query.split("/")[-1].replace("-", " ").title()
        return (
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
                    return (
                        res_o.get("Title"),
                        story,
                        res_o.get("Poster"),
                        "أفلام",
                        "PT02H00M",
                        res_o.get("imdbRating"),
                        res_o.get("Runtime"),
                        res_o.get("Year"),
                    )
                else:
                    print(
                        f"🛑 رفض النتيجة: OMDb أعاد '{omdb_title}' وهي لا تطابق '{clean_query}'"
                    )

        # --- المرحلة الثالثة: الصرامة المطلقة (بديل البحث المرن والـ AI) ---
        # --- المرحلة الثالثة: الصرامة المطلقة ---
        if not tmdb_final_id:
            # نستخدم search_query هنا عشان اللوج يظهر فيه (مسلسل علي كلاي 2026)
            print(
                f"🛑 لم يتم العثور على تطابق رسمي لـ '{search_query}'. تم إلغاء البحث المرن والـ AI لمنع البيانات الخاطئة."
            )
            return (
                search_query,
                "جاري تحديث القصة...",
                "",
                "أفلام",
                "PT01H30M",
                "N/A",
                "غير محدد",
                year or "2026",
            )

        if tmdb_final_id:
            # استخدام النوع المستخرج (movie أو tv) لطلب البيانات بشكل صحيح
            media_type = content_kind if "content_kind" in locals() else "movie"

            # 1. جلب البيانات بالإنجليزي
            en_url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_final_id}?api_key={TMDB_API_KEY}"
            en_data = requests.get(en_url).json()

            # في المسلسلات الاسم يكون 'name' وفي الأفلام 'title'
            title = en_data.get("title") or en_data.get("name") or title

            # تاريخ الإصدار يختلف أيضاً بين الفيلم والمسلسل
            tmdb_date = (
                en_data.get("release_date") or en_data.get("first_air_date") or "0000"
            )
            release_year = tmdb_date[:4]

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
                runtime_str = (
                    f"{runtime // 60} ساعة و {runtime % 60} دقيقة"
                    if runtime >= 60
                    else f"{runtime} دقيقة"
                )

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

        return title, story, poster, labels, duration, rating, runtime_str, release_year

    except Exception as e:
        print(f"⚠️ خطأ في الخوارزمية المزدوجة: {e}")
        return title, story, poster, labels, duration, rating, runtime_str, release_year


def upload_poster_to_cloudinary(image_url):
    """رفع البوستر ومعالجته لكلاود ناري"""
    try:
        cloudinary_api = f"https://api.cloudinary.com/v1_1/{CLOUDINARY_CONFIG['cloud_name']}/image/upload"
        payload = {
            "file": image_url,
            "upload_preset": CLOUDINARY_CONFIG["upload_preset"],
            "folder": "blogger",
        }
        res = requests.post(cloudinary_api, data=payload).json()
        public_id = res.get("public_id")
        return f"https://res.cloudinary.com/{CLOUDINARY_CONFIG['cloud_name']}/image/upload/q_auto,f_auto,w_600,h_900,c_fill,g_auto/{public_id}.webp"
    except:
        return image_url  # في حال الفشل يرجع الرابط الأصلي


def upload_to_voe_api(file_path, identifier):
    try:
        file_name = os.path.basename(file_path).replace(" ", "%20")
        remote_url = f"https://archive.org/download/{identifier}/{file_name}"
        params = {"key": VOE_API_KEY, "url": remote_url}

        # 1. طلب الرفع
        res = requests.get(
            "https://voe.sx/api/upload/url", params=params, timeout=30
        ).json()
        if res.get("status") != 200:
            return None

        file_code = res.get("result", {}).get("file_code")

        print(f"⏳ جاري متابعة حالة الرفع على Voe...")
        start_time = time.time()

        # تعريف شريط واحد فقط بتنسيق كامل ونظيف
        # ... قبل الحلقة ...
        check_count = 0
        pbar_voe = tqdm(total=100, desc="⏳ Voe Polling")

        while time.time() - start_time < 800:
            try:
                status_res = requests.get(
                    f"https://voe.sx/api/file/status?key={VOE_API_KEY}&file_code={file_code}",
                    timeout=20,
                ).json()
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

            time.sleep(25)

        pbar_voe.close()
        return file_code
    except Exception as e:
        print(f"⚠️ خطأ Voe API: {e}")
        return None


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
            pbar_vk = tqdm(
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
            response = requests.post(upload_url, files=files, timeout=None)

            pbar_vk.close()
            stream.close()

            print(f"DEBUG: VK File Upload Response Status: {response.status_code}")
            print(f"DEBUG: VK File Upload Response Text: {response.text}")

            if response.status_code == 200:
                # الحقيقة الصارمة: بمجرد وصول الحالة 200، الفيديو أصبح لدى VK
                # لا نحتاج لفك تشفير الـ JSON طالما نملك الـ IDs مسبقاً
                print(
                    f"✅ VK Upload Success: https://vk.com/video{owner_id}_{video_id}"
                )
                return f"https://vk.com/video{owner_id}_{video_id}"
            else:
                print(
                    f"❌ VK Upload: HTTP Error {response.status_code}. Response: {response.text}"
                )
                return None
    except Exception as e:
        print(f"⚠️ فشل VK المحلي: {e}")
        return None


async def upload_to_doodstream(file_path, api_key):
    print(f"🚀 جاري الرفع إلى DoodStream...")
    try:
        async with httpx.AsyncClient(timeout=600.0, follow_redirects=True) as client:
            # 1. الحصول على سيرفر الرفع المتاح
            # 1. قائمة النطاقات الاحتياطية (سيجربها الوحش بالترتيب)
            dood_domains = [
                "doodstream.com",
                "doodapi.com",
                "d0000d.com",
                "dood.to",
                "mdisk.me",
                "dood.so",
            ]
            upload_url = None

            for domain in dood_domains:
                try:
                    print(f"📡 محاولة الاتصال بـ DoodStream عبر: {domain}")
                    server_res = await client.get(
                        f"https://{domain}/api/upload/server?key={api_key}",
                        timeout=10.0,
                    )

                    if server_res.status_code == 200 and server_res.text.strip():
                        await asyncio.sleep(1) # تأخير ثانية لضمان استقرار السيرفر
                        try:
                            data = server_res.json()
                        except:
                            continue # لو الرد مش JSON جرب النطاق اللي بعده
                        if data.get("result"):
                            upload_url = data.get("result")
                            print(f"✅ تم الاتصال بنجاح عبر: {domain}")
                            break  # اخرج من الحلقة لأننا وجدنا سيرفر يعمل
                except Exception as e:
                    print(f"⚠️ النطاق {domain} غير مستجيب، يجرب التالي...")
                    continue


            if not upload_url:
                print(f"❌ فشل الحصول على سيرفر رفع من جميع النطاقات.")
                return None

            # 2. الرفع الفعلي للملف
            with open(file_path, "rb") as f:
                files = {"file": f}
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
                response = await client.post(
                    f"{upload_url}?key={api_key}", files=files, headers=headers
                )

                if response.status_code != 200:
                    return None

                result = response.json()
                if result.get("msg") == "OK":
                    file_code = result["result"][0]["file_code"]
                    iframe_url = f"https://doodstream.com/e/{file_code}"
                    print(f"✅ تم الرفع لـ DoodStream: {iframe_url}")
                    return iframe_url
                else:
                    print(f"❌ خطأ DoodStream: {result.get('msg')}")
                    return None
    except Exception as e:
        print(f"⚠️ عطل في DoodStream: {e}")
        return None


async def upload_to_streamtape(file_path, login, key):
    print(f"🎬 جاري الرفع إلى Streamtape...")
    try:
        async with httpx.AsyncClient(timeout=600.0, follow_redirects=True) as client:
            # 1. طلب رابط الرفع المتاح
            res = await client.get(
                f"https://api.streamtape.com/upload/server?login={login}&key={key}"
            )
            await asyncio.sleep(1) # انتظار بسيط

            if res.status_code != 200:
                return None

            try:
                data = res.json()
            except Exception:
                print(f"❌ Streamtape API Error: {res.text}")
                return None
            # حماية: فحص وجود النتيجة قبل القراءة
            if res.text.strip() == "OK":
                print("⚠️ Streamtape رد بـ OK (السيرفر مشغول)، جاري المحاولة مرة أخرى...")
                await asyncio.sleep(2)
                res = await client.get(f"https://api.streamtape.com/upload/server?login={login}&key={key}")
                data = res.json()

            if data.get("status") != 200 or not data.get("result"):
                print(f"❌ Streamtape لم يعطِ رابط رفع: {data.get('msg')}")
                return None

            upload_url = data["result"]["url"]

            # 2. الرفع الفعلي للملف
            with open(file_path, "rb") as f:
                files = {"file": f}
                response = await client.post(upload_url, files=files)

                if response.status_code != 200:
                    return None

                result = response.json()
                if result.get("status") == 200:
                    file_code = result["result"]["id"]
                    stream_url = f"https://streamtape.com/e/{file_code}"
                    print(f"✅ تم الرفع لـ Streamtape: {stream_url}")
                    return stream_url
                else:
                    print(f"❌ خطأ Streamtape أثناء الرفع")
                    return None
    except Exception as e:
        print(f"⚠️ عطل تقني في Streamtape: {e}")
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


# ابحث عن الدالة وغير السطر الخاص بالـ re.sub
def get_clean_media_data(raw_name):
    is_series = any(word in raw_name for word in ["مسلسل", "الحلقة", "حلقة", "موسم"])
    category = "tv" if is_series else "movie"

    # تعديل الـ Regex ليكون أكثر قوة وحذف أي شيء يبدأ من ( - الحلقة)
    clean_title = re.sub(
        r"[-–]?\s*(?:الحلقة|حلقة|الموسم|موسم)\s*\d+.*", "", raw_name
    ).strip()

    ep_match = re.search(r"(?:الحلقة|حلقة)\s*(\d+)", raw_name)
    ep_no = int(ep_match.group(1)) if ep_match else 1

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
