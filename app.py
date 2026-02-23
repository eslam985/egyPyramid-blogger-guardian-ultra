from fastapi import FastAPI, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from services.supabase_db import SupabaseService
from services.blogger_api import BloggerService
import os
import uvicorn
from datetime import datetime
from fastapi import BackgroundTasks
from dotenv import load_dotenv


# ثم قم بتعريف المتغير الذي يشتكي منه الكود:
supabase = SupabaseService.client
load_dotenv()  # شحن المتغيرات أولاً

# ثم بقية الاستدعاءات
from publisher.main_publisher import start_publishing_from_supabase

# التأكد من المفتاح
BLOG_ID = os.getenv("BLOG_ID")
if not BLOG_ID:
    raise ValueError("❌ BLOG_ID is missing from .env file!")

blogger = BloggerService(blog_id=BLOG_ID)

# --- المسارات (Routes) ---

print("--- Project Structure ---")
for root, dirs, files in os.walk("."):
    # تجاهل المجلدات المخفية مثل .git
    dirs[:] = [d for d in dirs if not d.startswith(".")]
    level = root.replace(".", "").count(os.sep)
    indent = " " * 4 * (level)
    print(f"{indent}{os.path.basename(root)}/")
    subindent = " " * 4 * (level + 1)
    for f in files:
        print(f"{subindent}{f}")
print("--------------------------")

# 1. تعريف التطبيق والإعدادات الأساسية
# 1. تعريف التطبيق
app = FastAPI()

# ده السطر اللي هيريحك من قصة الـ HTTP/HTTPS
app.mount("/static", StaticFiles(directory="static"), name="static")

# 3. الإعدادات الأخرى
templates = Jinja2Templates(directory="templates")
security = HTTPBasic()


# 2. نظام الحماية (Authentication)
def authenticate(credentials: HTTPBasicCredentials = Depends(security)):
    correct_email = os.getenv("ADMIN_EMAIL")
    correct_password = os.getenv("ADMIN_PASSWORD")
    if (
        credentials.username != correct_email
        or credentials.password != correct_password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="خطأ في بيانات الدخول",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


@app.post("/publisher/run")
async def run_publisher(
    background_tasks: BackgroundTasks, user: str = Depends(authenticate)
):
    # استخدام BackgroundTasks ضروري جداً هنا
    # لأن عملية النشر قد تأخذ دقائق، ولا نريد للمتصفح أن ينتظر (Timeout)
    background_tasks.add_task(start_publishing_from_supabase)
    return {"status": "success", "message": "بدأت عملية النشر في الخلفية..."}


# إضافة عمل جديد
@app.post("/api/media/add")
async def add_new_work(
    user: str = Depends(authenticate),
    title: str = Form(...),
    category: str = Form(...),
    story: str = Form(...),
    year: str = Form(None),  # تغيير من int لـ str لتوافق قاعدة البيانات
    rating: str = Form(None),
    tmdb_id: str = Form(None),
    labels: str = Form(None),
    runtime: str = Form(None),
    poster_url: str = Form(...),
):
    payload = {
        "title": title,
        "category": category,
        "story": story,
        "year": year,
        "rating": rating,
        "tmdb_id": tmdb_id,
        "labels": labels,
        "runtime": runtime,
        "poster_url": poster_url,
    }
    new_media = SupabaseService.add_media(payload)

    if new_media:
        media_id = new_media["id"]
        # 2. إنشاء مسودة في بلوجر فوراً لهذا العمل الجديد
        blogger_res = blogger.create_post(
            title=title,
            content=f"<p>{story}</p>",
            is_draft=True,  # ينشر كمسودة كما تفضل
        )

        # 3. حفظ الـ Blogger ID الناتج في ساب باز داخل العمل نفسه
        if "id" in blogger_res:
            SupabaseService.update_media(
                media_id, {"blogger_post_id": blogger_res["id"]}
            )

    return {"status": "success", "data": new_media}


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
    poster_url: str = Form(...),
):
    data = {
        "title": title,
        "story": story,
        "category": category,
        "year": year,
        "rating": rating,
        "tmdb_id": tmdb_id,
        "labels": labels,
        "runtime": runtime,
        "poster_url": poster_url,
    }
    SupabaseService.update_media(media_id, data)
    return {"status": "success"}


# حذف عمل
@app.post("/api/media/delete/{media_id}")
async def delete_media(media_id: int, user: str = Depends(authenticate)):
    SupabaseService.delete_media(media_id)
    return {"status": "deleted"}


# تحويل مقال بلوجر لمسودة
@app.post("/api/blogger/revert/{post_id}")
async def revert_post(post_id: str, user: str = Depends(authenticate)):
    res = blogger.change_post_status(post_id, revert=True)
    return res


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


@app.get("/api/media/details/{media_id}")
async def get_media_details(media_id: int, user: str = Depends(authenticate)):
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


@app.post("/api/media/{media_id}/add-episode")
async def add_episode(
    media_id: int, episode_number: int = Form(...), user: str = Depends(authenticate)
):
    try:
        data = {
            "media_id": media_id,
            "episode_number": episode_number,
            "is_synced": False,  # تبدأ غير منشورة حتى تضغط أنت على المزامنة
        }
        SupabaseService.client.table("episodes").insert(data).execute()
        return {"status": "success"}
    except Exception as e:
        return {"error": str(e)}


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


# إضافة رابط جديد
@app.post("/api/episodes/{ep_id}/add-link")
async def add_link(ep_id: int):
    # التعديل: استخدام url بدلاً من link_url
    SupabaseService.client.table("links").insert(
        {"episode_id": ep_id, "server_name": "سيرفر جديد", "url": ""}
    ).execute()
    return {"status": "success"}


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


# مسار المزامنة الفعلي مع بلوجر
@app.post("/api/episodes/{ep_id}/sync")
async def sync_episode_to_blogger(ep_id: int, user: str = Depends(authenticate)):
    try:
        # 1. جلب بيانات الحلقة
        ep_res = (
            SupabaseService.client.table("episodes")
            .select("*")
            .eq("id", ep_id)
            .single()
            .execute()
        )

        # 2. التأكد من وجود روابط
        links_res = (
            SupabaseService.client.table("links")
            .select("*")
            .eq("episode_id", ep_id)
            .execute()
        )
        if not links_res.data:
            return {
                "status": "error",
                "error": "لا توجد روابط! أضف روابط أولاً ثم اضغط مزامنة.",
            }

        # الحقيقة الصارمة: لا نغير is_synced لـ True هنا!
        # نتركها False لكي يراها الكولاب، لكن نحدث blogger_sync لنعطي إشارة للكولاب بالبدء
        SupabaseService.client.table("episodes").update(
            {
                "is_synced": False,  # تبقى فولس كما هي لكي يراها الكولاب
                "blogger_sync": "Approved",  # إشارة "الضوء الأخضر" للكولاب
                "updated_at": datetime.utcnow().isoformat(),
            }
        ).eq("id", ep_id).execute()

        return {
            "status": "success",
            "message": "تم اعتماد الحلقة بنجاح. يرجى الضغط على زر (تشغيل المحرك) لبدء النشر الفوري.",
        }

    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.post("/api/blogger/toggle/{post_id}")
async def toggle_post_status(post_id: str, username: str = Depends(authenticate)):
    try:
        from services.blogger_api import BloggerService

        blogger = BloggerService(blog_id=os.getenv("BLOG_ID"))
        service = blogger.get_service()

        # جلب البيانات الحالية بدقة
        post = (
            service.posts().get(blogId=os.getenv("BLOG_ID"), postId=post_id).execute()
        )
        current_status = post.get("status")  # القيم الممكنة: LIVE أو DRAFT

        if current_status == "LIVE":
            # أمر التحويل لمسودة (Revert)
            service.posts().revert(
                blogId=os.getenv("BLOG_ID"), postId=post_id
            ).execute()
            new_status = "draft"
        else:
            # أمر النشر (Publish)
            service.posts().publish(
                blogId=os.getenv("BLOG_ID"), postId=post_id
            ).execute()
            new_status = "live"

        return {"status": "success", "new_status": new_status}
    except Exception as e:
        print(f"Error toggling post {post_id}: {e}")
        return {"status": "error", "error": str(e)}


# الصفحة الرئيسية (محمية بكلمة سر)
@app.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    page: int = 1, # أضفنا هذا
    search: str = None,
    cat: str = None,
    status: str = None, # أضفنا هذا
    user: str = Depends(authenticate),
):
    page_size = 12
    offset = (page - 1) * page_size

    # بناء الاستعلام يدوياً لدعم الترقيم والفلترة
    query = SupabaseService.client.table("medias").select("*", count="exact")

    if search:
        query = query.ilike("title", f"%{search}%")
    if cat:
        query = query.eq("category", cat)
    if status == "not_published":
        query = query.is_("blogger_post_id", "null")
    elif status == "published":
        query = query.not_.is_("blogger_post_id", "null")

    # تنفيذ الاستعلام
    res = query.order("created_at", desc=True).range(offset, offset + page_size - 1).execute()

    # حساب الترقيم
    total_count = res.count if res.count is not None else 0
    total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 1

    return templates.TemplateResponse(
        "index.html", {
            "request": request,
            "media_list": res.data,
            "search": search or "",
            "current_page": page,        # هذا سيحل خطأ Jinja2
            "total_pages": total_pages,  # وهذا أيضاً
            "current_cat": cat or "",
            "current_status": status or ""
        }
    )


# حذف رابط معين
@app.post("/api/links/{link_id}/delete")
async def delete_link_api(link_id: int, user: str = Depends(authenticate)):
    SupabaseService.client.table("links").delete().eq("id", link_id).execute()
    return {"status": "deleted"}


if __name__ == "__main__":
    # تأكد من عدم وجود مسافات زائدة أو استدعاءات مكررة
    uvicorn.run("app:app", host="0.0.0.0", port=7860, reload=True)
