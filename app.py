import uvicorn, logging, json, re, html, requests, sys, os, jwt
from dotenv import load_dotenv
from fastapi import (
    FastAPI,
    Request,
    Form,
    Depends,
    HTTPException,
    status,
    BackgroundTasks,
    Body,
)
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from bs4 import BeautifulSoup
from services.supabase_db import SupabaseService

# محاولة استيراد BloggerService
try:
    from services.blogger_api import BloggerService
except ImportError:
    BloggerService = None

# إعداد البيئة واللوجات
load_dotenv()
logging.basicConfig(level=logging.INFO)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

# 1. تهيئة التطبيق والميدلوير (يجب أن يكونا أول شيء)
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. إعداد المتغيرات الأساسية
BLOG_ID = os.getenv("BLOG_ID")
SECRET_KEY = os.getenv("SECRET_KEY")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login")

# 3. تهيئة الخدمات
blogger = BloggerService(blog_id=BLOG_ID) if BLOG_ID and BloggerService else None

# 4. تهيئة الخدمات
supabase = getattr(SupabaseService, "client", None)


def authenticate(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload.get("sub")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="غير مصرح بالدخول",
            headers={"WWW-Authenticate": "Bearer"},
        )


def convert_vk_to_embed(url):
    if (
        not url
        or not any(domain in url for domain in ["vk.com", "vkvideo.ru"])
        or "video_ext.php" in url
    ):
        return url
    try:

        match_ids = re.search(r"video(-?\d+)_(\d+)", url)
        if not match_ids:
            return url

        fixed_oid = match_ids.group(1)
        fixed_id = match_ids.group(2)

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }

        response = requests.get(url, headers=headers, timeout=10)
        # تنظيف محتوى الصفحة من رموز مثل &amp; قبل البحث عن الهاش
        clean_content = html.unescape(response.text)

        # البحث عن الهاش بنمط أكثر دقة
        hash_match = re.search(r'hash[":=]+([a-z0-9]+)', clean_content)

        if hash_match:
            final_hash = hash_match.group(1)
            # نستخدم vkvideo.ru ونضع الهاش والـ & بشكل نظيف
            return f"https://vkvideo.ru/video_ext.php?oid={fixed_oid}&id={fixed_id}&hash={final_hash}&hd=2"
        else:
            return f"https://vkvideo.ru/video_ext.php?oid={fixed_oid}&id={fixed_id}"

    except Exception as e:
        print(f"⚠️ VK Hash Error: {e}")
        return url


@app.post("/api/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    if form_data.username != os.getenv(
        "ADMIN_EMAIL"
    ) or form_data.password != os.getenv("ADMIN_PASSWORD"):
        raise HTTPException(status_code=400, detail="بيانات دخول خاطئة")
    token = jwt.encode({"sub": form_data.username}, SECRET_KEY, algorithm="HS256")
    return {"access_token": token, "token_type": "bearer"}


# 7. المسارات (الـ APIs توضع هنا...)
# ... (ضع الـ @app.post والـ @app.get الخاصة بك هنا) ...
@app.get("/api/media/list", include_in_schema=True)
async def get_media_list(
    search: str = None, cat: str = None, status: str = None, page: int = 1
):
    # جلب البيانات من Supabase
    data, total_count = SupabaseService.get_media(
        search_query=search, category=cat, status=status, page=page, limit=12
    )
    return {"data": data or [], "total_count": total_count}


@app.get("/api/media/details/{media_id}")
async def get_media_details(
    media_id: int, user: str = Depends(authenticate)
):  # أضفنا الحماية هنا
    try:
        # جلب بيانات الميديا
        media_res = (
            SupabaseService.client.table("medias")
            .select("*")
            .eq("id", media_id)
            .single()
            .execute()
        )
        # جلب الحلقات المرتبطة بها مرتبة برقم الحلقة
        episodes_res = (
            SupabaseService.client.table("episodes")
            .select("*")
            .eq("media_id", media_id)
            .order("episode_number")
            .execute()
        )

        if not media_res.data:
            return {"error": "العمل غير موجود"}

        data = media_res.data
        data["episodes"] = episodes_res.data if episodes_res.data else []
        return data
    except Exception as e:
        return {"error": str(e)}


# حذف عمل
@app.post("/api/media/delete/{media_id}")
async def delete_media(media_id: int, user: str = Depends(authenticate)):
    SupabaseService.delete_media(media_id)
    return {"status": "deleted"}


# تعديل عمل
@app.post("/api/media/update/{media_id}")
async def update_media(
    media_id: int,
    user: str = Depends(authenticate),
    title: str = Form(...),
    story: str = Form(...),
    category: str = Form(...),
    year: str = Form(None),
    rating: str = Form(None),
    tmdb_id: str = Form(None),
    labels: str = Form(None),
    runtime: str = Form(None),
    duration_iso: str = Form(None),
    poster_url: str = Form(...),
):
    # يجب أن يبدأ الكود بـ try لتتمكن من استخدام except لاحقاً
    try:
        data = {
            "title": title,
            "story": story,
            "category": category,
            "year": year,
            "rating": rating,
            "tmdb_id": tmdb_id,
            "labels": labels,
            "runtime": runtime,
            "duration_iso": duration_iso,
            "poster_url": poster_url,
        }
        print(f"DEBUG: Updating media {media_id} with data: {data}")
        SupabaseService.update_media(media_id, data)
        return {"status": "success"}
    except Exception as e:
        print(f"❌ CRITICAL ERROR in update_media: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/media/add")
async def add_new_work(
    user: str = Depends(authenticate),
    # استخدم Body بدلاً من Form لاستقبال JSON
    payload: dict = Body(...),
):
    # الآن payload هو القاموس (dictionary) القادم من Vue مباشرة
    # لا حاجة لاستخراج كل حقل على حدة
    new_media = SupabaseService.add_media(payload)

    if new_media:
        media_id = new_media["id"]
        # إنشاء مسودة في بلوجر
        blogger_res = blogger.create_post(
            title=payload.get("title"),
            content=f"<p>{payload.get('story')}</p>",
            is_draft=True,
        )

        if blogger_res and "id" in blogger_res:
            SupabaseService.update_media(
                media_id, {"blogger_post_id": blogger_res["id"]}
            )

    return {"status": "success", "data": new_media}


# التعديل: تحويل المسار لنظام FastAPI وتصحيح استدعاء السوبابيز
@app.post("/api/episodes/{ep_id}/reset-sync")
async def force_sync(ep_id: int, user: str = Depends(authenticate)):
    try:
        # الحقيقة الصارمة: نستخدم الكلاينت الموجود داخل السيرفيس
        SupabaseService.client.table("episodes").update({"is_synced": False}).eq(
            "id", ep_id
        ).execute()
        return {"status": "success"}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/media/{media_id}/add-episode")
async def add_episode(
    media_id: int, episode_number: int = Form(...), user: str = Depends(authenticate)
):
    try:
        # 1. التحقق من التكرار أولاً في ساب باز
        check = (
            SupabaseService.client.table("episodes")
            .select("id")
            .eq("media_id", media_id)
            .eq("episode_number", episode_number)
            .execute()
        )

        if check.data:
            return {
                "status": "error",
                "error": f"الحلقة {episode_number} موجودة بالفعل!",
            }

        # 2. إذا لم تكن موجودة، قم بالإدخال
        data = {
            "media_id": media_id,
            "episode_number": episode_number,
            "is_synced": False,
        }
        SupabaseService.client.table("episodes").insert(data).execute()
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


# مسار المزامنة الفعلي مع بلوجر
@app.post("/api/episodes/{ep_id}/sync")
async def sync_episode_to_blogger(
    ep_id: int, background_tasks: BackgroundTasks, user: str = Depends(authenticate)
):
    try:
        # إضافة حماية: التأكد من وجود الخدمة
        if blogger is None:
            print("❌ Error: Blogger instance is None. Check BLOG_ID in .env")
            return {
                "status": "error",
                "error": "خدمة Blogger غير مهيأة (Check BLOG_ID)",
            }
        # 1. جلب بيانات الحلقة والعمل المرتبط بها
        ep_res = (
            supabase.table("episodes")
            .select("*, medias(blogger_post_id)")
            .eq("id", ep_id)
            .single()
            .execute()
        )
        if not ep_res.data:
            return {"status": "error", "error": "الحلقة غير موجودة"}

        episode = ep_res.data
        post_id = episode.get("medias", {}).get("blogger_post_id")

        # إذا لم يوجد مقال، سنعطي أمر للمحرك بالعمل فوراً
        if not post_id:
            from publisher.main_publisher import start_publishing_from_supabase

            # تحديث الحالة لكي يراها المحرك
            supabase.table("episodes").update({"blogger_sync": "Approved"}).eq(
                "id", ep_id
            ).execute()
            # تشغيل المحرك في الخلفية
            background_tasks.add_task(start_publishing_from_supabase)
            return {
                "status": "success",
                "message": "🆕 عمل جديد! جاري إنشاء المقال في الخلفية...",
            }

        # 2. جلب الروابط وتجهيز الـ HTML الجديد للحلقة
        links_res = (
            supabase.table("links").select("*").eq("episode_id", ep_id).execute()
        )
        if not links_res.data:
            return {"status": "error", "error": "لا توجد روابط لهذه الحلقة!"}

        # --- [1] معالجة وتصحيح الروابط (النظام الديناميكي الشامل) ---
        episode_links = []
        excluded_servers = ["telegram_direct", "archive", "download"]
        down_url = ""

        for l in links_res.data:
            s_name = l["server_name"].lower()
            u = l["url"]

            if s_name == "download":
                down_url = u
                continue

            if s_name in excluded_servers or not u:
                continue

            # تصحيحات الروابط
            if s_name == "vidtube" and "embed-" not in u:
                u = u.replace("vidtube.one/", "vidtube.one/embed-")
            if s_name == "vk":
                u = convert_vk_to_embed(u)
            if s_name == "archive" and "details/" in u:
                u = u.replace("details/", "embed/")

            episode_links.append({"name": s_name, "url": u})

        links_json = json.dumps(episode_links).replace('"', "&quot;")

        # --- [2] بناء الـ HTML بنظام playEpDynamic الجديد ---
        new_ep_html = f"""<div class="ep-btn" onclick="playEpDynamic(this, '{episode['episode_number']}', '{down_url}', '{links_json}')">{episode['episode_number']}</div>"""

        # --- [2] جلب المحتوى وبدء المعالجة بـ BeautifulSoup ---
        # --- [2] جلب المحتوى وبدء المعالجة بـ BeautifulSoup ---
        # التعديل لضمان عدم وجود NoneType
        if blogger is None:
            current_blogger = BloggerService(blog_id=BLOG_ID)
        else:
            current_blogger = blogger

        service = current_blogger.get_service()
        post = service.posts().get(blogId=BLOG_ID, postId=post_id).execute()
        soup = BeautifulSoup(post["content"], "html.parser")

        # --- [3] تحديث زر التحميل الرئيسي (أعلى المقال) ---
        main_download_btn = soup.find("a", id="download-btn")
        if main_download_btn and down_url:
            main_download_btn["href"] = down_url
            main_download_btn.string = (
                f" 📥 تحميل الحلقة {episode['episode_number']} HD "
            )

        # --- [4] حقن الحلقة في الحاوية (Injection) ---
        container = soup.find(class_="ep-More")
        if not container:
            return {"status": "error", "error": "كلاس ep-More غير موجود في المقال!"}

        # التحقق لمنع التكرار
        if f">{episode['episode_number']}</div>" in str(container):
            return {"status": "success", "message": "الحلقة موجودة بالفعل!"}

        # الحقن الفعلي
        container.insert(0, BeautifulSoup(new_ep_html, "html.parser"))

        # --- [5] حفظ التغييرات في بلوجر وسوبابيز ---
        post["content"] = str(soup)
        service.posts().update(blogId=BLOG_ID, postId=post_id, body=post).execute()

        supabase.table("episodes").update(
            {"is_synced": True, "blogger_sync": "Done"}
        ).eq("id", ep_id).execute()

        return {"status": "success", "message": "تم الحقن وتحديث زر التحميل بنجاح!"}

    except Exception as e:
        print(f"❌ Sync Error: {str(e)}")
        return {"status": "error", "error": str(e)}


# تحديث بيانات رابط (سيرفر) معين
@app.post("/api/links/{link_id}/update")
async def update_link_api(
    link_id: int,
    server_name: str = Form(None),
    url: str = Form(None),  # تعديل هنا
    user: str = Depends(authenticate),
):
    update_data = {}
    if server_name is not None:
        update_data["server_name"] = server_name
    if url is not None:
        update_data["url"] = url  # تعديل هنا

    SupabaseService.client.table("links").update(update_data).eq(
        "id", link_id
    ).execute()
    return {"status": "success"}


# جلب روابط حلقة معينة
@app.get("/api/episodes/{ep_id}/links")
async def get_links(ep_id: int):
    res = (
        SupabaseService.client.table("links")
        .select("*")
        .eq("episode_id", ep_id)
        .execute()
    )
    return res.data


# حذف رابط معين
@app.post("/api/links/{link_id}/delete")
async def delete_link_api(link_id: int, user: str = Depends(authenticate)):
    SupabaseService.client.table("links").delete().eq("id", link_id).execute()
    return {"status": "deleted"}


# إضافة رابط جديد
@app.post("/api/episodes/{ep_id}/add-link")
async def add_link(ep_id: int):
    # التعديل: استخدام url بدلاً من link_url
    SupabaseService.client.table("links").insert(
        {"episode_id": ep_id, "server_name": "سيرفر جديد", "url": ""}
    ).execute()
    return {"status": "success"}


@app.post("/api/episodes/{ep_id}/delete")
async def delete_episode_api(ep_id: int, user: str = Depends(authenticate)):
    try:
        # حذف الحلقة (سيحذف الروابط تلقائياً لو عندك Cascade)
        SupabaseService.client.table("episodes").delete().eq("id", ep_id).execute()
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.post("/api/publisher/run")
async def run_publisher(
    background_tasks: BackgroundTasks, user: str = Depends(authenticate)
):
    # استخدام BackgroundTasks ضروري جداً هنا
    # لأن عملية النشر قد تأخذ دقائق، ولا نريد للمتصفح أن ينتظر (Timeout)
    try:
        from publisher.main_publisher import start_publishing_from_supabase

        background_tasks.add_task(start_publishing_from_supabase)
    except ImportError:
        print("⚠️ Publisher function not available (Library missing)")
    return {"status": "success", "message": "بدأت عملية النشر في الخلفية..."}


# 2. مسار جلب التقدم (هذا ما سيقرأه شريط التقدم)
# 2. مسار جلب التقدم (النسخة المنضبطة)
@app.get("/api/download/progress")
async def get_all_progress(user: str = Depends(authenticate)):
    try:
        # الحقيقة الصارمة: نريد فقط المهام التي "تتحرك" فعلياً
        res = (
            SupabaseService.client.table("episodes")
            .select("id, status_message, progress_percent, download_speed")
            .neq("download_speed", "Done")  # استبعاد المنتهي
            .lt("progress_percent", 100)  # استبعاد من وصل 100%
            .order("id", desc=True)  # الترتيب حسب الأحدث
            .limit(5)
            .execute()
        )
        return res.data
    except Exception as e:
        print(f"❌ Error fetching progress: {e}")
        return []


# 1. مسار بدء التحميل
# 1. مسار بدء التحميل (نسخة التحكم عن بعد)
@app.post("/api/download/run")
async def run_download_task(
    url: str = Form(...),
    name: str = Form(...),
    user: str = Depends(authenticate),
):
    try:
        # الحقيقة الصارمة: تحديث البيانات أو إضافتها لضمان أن كاجل يراها
        # نستخدم upsert بناءً على الرابط
        data = {
            "download_url": url,
            "file_name": name,
            "status": "pending",
            "status_message": "في انتظار استجابة الوحش من Kaggle...",
            "progress_percent": 0,
            "download_speed": "Waiting...",
        }

        # تنفيذ التحديث بناءً على الرابط (أو id لو أردت)
        SupabaseService.client.table("episodes").upsert(
            data, on_conflict="download_url"
        ).execute()

        return {"status": "success", "message": "تم إرسال الإشارة للوحش!"}
    except Exception as e:
        print(f"❌ Error in run_download: {e}")
        return {"status": "error", "message": str(e)}


# 1. تحديد المسار بناءً على مكان ملف app.py (هذا يعمل في أي مكان)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIST = os.path.join(BASE_DIR, "static", "dist")

print(f"DEBUG: Calculated STATIC_DIST: {STATIC_DIST}")
print(f"DEBUG: Does it exist? {os.path.exists(STATIC_DIST)}")

# 2. التأكد من المجلدات
if os.path.exists(STATIC_DIST):
    # ربط ملفات الـ assets
    app.mount(
        "/assets",
        StaticFiles(directory=os.path.join(STATIC_DIST, "assets")),
        name="assets",
    )

    # 3. توجيه الصفحة الرئيسية
    @app.get("/")
    async def index():
        return FileResponse(os.path.join(STATIC_DIST, "index.html"))

    # 4. توجيه الـ SPA
    @app.get("/{rest_of_path:path}")
    async def serve_spa(rest_of_path: str):
        if rest_of_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API route not found")
        return FileResponse(os.path.join(STATIC_DIST, "index.html"))

else:
    print(f"⚠️ CRITICAL: STATIC_DIST not found at {STATIC_DIST}")


if __name__ == "__main__":
    # تأكد من عدم وجود مسافات زائدة أو استدعاءات مكررة
    uvicorn.run("app:app", host="0.0.0.0", port=7860, reload=True)
