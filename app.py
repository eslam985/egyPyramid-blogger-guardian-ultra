# /media/es/DDrive/projects/apps-python/egyPyramid-guardian-ultra/app.py
import uvicorn, logging, json, re, html, requests, sys, os, jwt, threading, asyncio
import worker  # استيراد ملف الووركر للوصول للمتغير العالمي
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

# تعديل عمل
from pydantic import BaseModel
from typing import Optional

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

# المسار اللي الوحش شغال فيه وبيرمي فيه الفيديوهات
# --- ⚡ نظام السحب المباشر (Guardian Direct Stream) ⚡ ---
# المسار العام في جذر السبيس
STREAM_DIR = os.path.join(os.getcwd(), "stream")
os.makedirs(STREAM_DIR, exist_ok=True)

# فتح المجلد للوصول العام
app.mount("/stream", StaticFiles(directory=STREAM_DIR), name="stream")
print(f"📡 [Direct Stream] البوابة مفتوحة الآن على: {STREAM_DIR}")
# ----------------------------------
# تشغيل "الوحش" وصياد الروابط (Feeder) في خلفية النظام عند بدء التشغيل
@app.on_event("startup")
async def startup_event():
    # 1. إطلاق الووركر الأساسي (الوحش) في Thread مستقل كالعادة
    try:
        from worker import ultimate_beast_worker
        thread = threading.Thread(target=ultimate_beast_worker, daemon=True)
        thread.start()
        print("🚀 [Background] Guardian Monster has been unleashed in the background...")
    except ImportError:
        print("⚠️ [Warning] worker.py not found. Monster is still in the cage.")
    except Exception as e:
        print(f"❌ [Error] Failed to start background worker: {e}")

    # 2. حلقة التغذية التلقائية للإسكربر (تشتغل في الخلفية كـ Async Task صامتة)
    async def auto_feeder_loop():
        import asyncio
        # استيراد الدالة الـ Async اللي جهزناها في ملف الإسكربر الجديد
        try:
            from scraper_feeder import run_scraper_async
            print("⏳ [Feeder] Auto-loop initialised. Will pulse every 1 hour.")
            while True:
                try:
                    await run_scraper_async()
                except Exception as fe:
                    print(f"❌ [Feeder Error] Error inside scraper cycle: {fe}")
                
                # انتظر ساعة واحدة (3600 ثانية) قبل اللفة الجاية
                #(إذا كنت تفضل جعلها كل ساعتين، يمكنك تغيير الرقم إلى 7200 وتعديل نص الـ print إلى 2 hours).
                await asyncio.sleep(3600)
        except ImportError:
            print("⚠️ [Warning] scraper_feeder.py not found. Auto-feeder is disabled.")

    # حقن اللوب جوة الـ FastAPI Event Loop عشان يشتغل أوتوماتيك
    asyncio.create_task(auto_feeder_loop())


# الصحيح هو وضع كل المواقع المسموح بها في قائمة واحدة فقط
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://eslam985.github.io"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. إعداد المتغيرات الأساسية
BLOG_ID: str = os.getenv("BLOG_ID") or ""
SECRET_KEY: str = os.getenv("SECRET_KEY") or "default_secret_key_change_it"
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
    admin_email = os.getenv("ADMIN_EMAIL")
    admin_password = os.getenv("ADMIN_PASSWORD")

    if form_data.username != admin_email or form_data.password != admin_password:
        raise HTTPException(status_code=400, detail="بيانات دخول خاطئة")

    token = jwt.encode({"sub": form_data.username}, SECRET_KEY, algorithm="HS256")
    return {"access_token": token, "token_type": "bearer"}


@app.get("/api/search/id/{media_id}")
def search_by_id(media_id: int):
    return SupabaseService.find_media_by_id(media_id)

# 7. المسارات (الـ APIs توضع هنا...)
# ... (ضع الـ @app.post والـ @app.get الخاصة بك هنا) ...
@app.get("/api/media/list", include_in_schema=True)
async def get_media_list(
    search: Optional[str] = None,
    cat: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
):
    # جلب البيانات من Supabase مع ضمان عدم تمرير None
    data, total_count = SupabaseService.get_media(
        search_query=search or "",
        category=cat or "",
        status=status or "",
        page=page,
        limit=12,
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


# 1. عرف الموديل أولاً
# 1. عرف الموديل أولاً مع Optional لكل الحقول
class MediaUpdate(BaseModel):
    title: Optional[str] = None
    story: Optional[str] = None
    category: Optional[str] = None
    poster_url: Optional[str] = None
    year: Optional[str] = None
    rating: Optional[str] = None
    tmdb_id: Optional[str] = None
    labels: Optional[str] = None
    runtime: Optional[str] = None
    duration_iso: Optional[str] = None
    blogger_status: Optional[str] = None
    media_type: Optional[str] = None
    slug: Optional[str] = None


@app.post("/api/media/update/{media_id}")
async def update_media(
    media_id: int, data: MediaUpdate, user: str = Depends(authenticate)
):
    try:
        # تحويل الموديل إلى dictionary
        update_data = data.dict(exclude_unset=True)
        print(f"DEBUG: Updating media {media_id} with data: {update_data}")
        SupabaseService.update_media(media_id, update_data)
        return {"status": "success"}
    except Exception as e:
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

    if new_media and blogger:
        media_id = new_media["id"]
        # إنشاء مسودة في بلوجر
        try:
            blogger_res = blogger.create_post(
                title=payload.get("title"),
                content=f"<p>{payload.get('story')}</p>",
                is_draft=True,
            )

            if blogger_res and "id" in blogger_res:
                SupabaseService.update_media(
                    media_id, {"blogger_post_id": blogger_res["id"]}
                )
        except Exception as e:
            print(f"⚠️ Blogger Error: {e}")

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
        # في app.py داخل دالة sync_episode_to_blogger
        # إذا لم يوجد مقال (عمل جديد)، سنقوم بتشغيل المحرك فوراً بشكل مباشر
        if not post_id:
            try:
                from publisher.main_publisher import start_publishing_from_supabase

                print(f"🚀 بدء عملية النشر المباشر للحلقة {ep_id}...")

                # تنفيذ مباشر بدون background_tasks
                print("--- [DEBUG] قبل استدعاء المحرك ---")
                start_publishing_from_supabase()
                print("--- [DEBUG] بعد استدعاء المحرك ---")

                return {
                    "status": "success",
                    "message": "✅ تم إنشاء المقال ونشره بنجاح!",
                }
            except Exception as e:
                # هنا سيظهر الخطأ الحقيقي في التيرمينال وفي المتصفح
                print(f"❌ خطأ فادح أثناء النشر المباشر: {str(e)}")
                return {"status": "error", "error": f"فشل النشر: {str(e)}"}

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


# --- مسارات إدارة قاعدة البيانات الشاملة ---


@app.get("/api/db/tables")
async def get_tables(user: str = Depends(authenticate)):
    # هذه الجداول التي سنسمح بإدارتها
    return ["medias", "episodes", "links", "genres", "seasons", "media_genres"]


@app.get("/api/db/{table_name}")
async def get_table_data(
    table_name: str, page: int = 1, limit: int = 50, user: str = Depends(authenticate)
):
    try:
        start = (page - 1) * limit
        end = start + limit - 1

        query = SupabaseService.client.table(table_name).select("*", count="exact")

        # ترتيب ذكي: لو الجدول فيه id رتب بيه، لو لا (زي media_genres) رتب بأول عمود
        if table_name == "media_genres":
            res = query.order("media_id", desc=True).range(start, end).execute()
        else:
            res = query.order("id", desc=True).range(start, end).execute()

        return {"data": res.data, "total": res.count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/db/{table_name}/insert")
async def insert_table_data(
    table_name: str, data: dict = Body(...), user: str = Depends(authenticate)
):
    try:
        res = SupabaseService.client.table(table_name).insert(data).execute()
        return {"status": "success", "data": res.data[0] if res.data else None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/db/{table_name}/update/{row_id}")
async def update_table_row(
    table_name: str,
    row_id: int,
    data: dict = Body(...),
    user: str = Depends(authenticate),
):
    try:
        res = (
            SupabaseService.client.table(table_name)
            .update(data)
            .eq("id", row_id)
            .execute()
        )
        return {"status": "success", "data": res.data[0] if res.data else None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/db/{table_name}/delete/composite")
async def delete_composite_row(
    table_name: str, data: dict = Body(...), user: str = Depends(authenticate)
):
    try:
        # الحذف باستخدام المفاتيح المركبة (مثلاً media_id و genre_id)
        query = SupabaseService.client.table(table_name).delete()
        for key, value in data.items():
            query = query.eq(key, value)
        query.execute()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/db/{table_name}/delete/{row_id}")
async def delete_table_row(
    table_name: str, row_id: int, user: str = Depends(authenticate)
):
    try:
        SupabaseService.client.table(table_name).delete().eq("id", row_id).execute()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/worker/status")
async def get_worker_status():
    """معرفة حالة الووركر حالياً (شغال ولا واقف)"""
    return {
        "status": "stopped" if worker.should_stop_worker else "running",
        "should_stop": worker.should_stop_worker,
    }


@app.post("/api/worker/stop")
async def stop_worker(user: str = Depends(authenticate)):
    """إرسال أمر إيقاف فوري للووركر"""
    worker.should_stop_worker = True
    logging.info("🛑 [API] تم استلام أمر إيقاف الووركر من الداشبورد.")
    return {"message": "تم إرسال أمر الإيقاف، سيخرج الووركر بعد إنهاء الدورة الحالية."}


@app.post("/api/worker/start")
async def start_worker(user: str = Depends(authenticate)):
    """إعادة تشغيل الووركر إذا كان متوقفاً"""
    if worker.should_stop_worker:
        worker.should_stop_worker = False
        # بما إننا شغالين daemon thread، اللوب هيرجع يشتغل لوحده في اللفة الجاية
        # أو ممكن نعيد تشغيل الـ thread لو فضل False تماماً
        logging.info("🚀 [API] تم إعادة تفعيل الووركر.")
        return {"message": "تم إعادة تفعيل الووركر بنجاح."}
    return {"message": "الووركر يعمل بالفعل."}


# --- خدمة ملفات الفرونت إيند (يجب أن تظل في النهاية المطلقة) ---
# تم نقل هذا الجزء لضمان عدم تعارضه مع أي مسار يبدأ بـ /api/
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIST = os.path.join(BASE_DIR, "static", "dist")

if os.path.exists(STATIC_DIST):
    app.mount(
        "/assets",
        StaticFiles(directory=os.path.join(STATIC_DIST, "assets")),
        name="assets",
    )

    @app.get("/")
    async def index():
        index_path = os.path.join(STATIC_DIST, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return {"status": "Backend is running successfully, but Front-end build (index.html) is missing from static/dist/"}

    @app.get("/{rest_of_path:path}")
    async def serve_spa(    rest_of_path: str):
        # قاعدة صارمة: إذا كان المسار يبدأ بـ api، فلا ترجع ملف الـ index.html أبداً
        if rest_of_path.startswith("api/") or rest_of_path.startswith("api"):
            raise HTTPException(status_code=404, detail="API Route Not Found")

        return FileResponse(os.path.join(STATIC_DIST, "index.html"))

else:
    print(f"⚠️ CRITICAL: STATIC_DIST not found at {STATIC_DIST}")


if __name__ == "__main__":
    # تأكد من عدم وجود مسافات زائدة أو استدعاءات مكررة
    uvicorn.run("app:app", host="0.0.0.0", port=7860, reload=True)
