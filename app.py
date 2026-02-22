from fastapi import FastAPI, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from services.supabase_db import SupabaseService
from services.blogger_api import BloggerService
import os

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


# 3. تهيئة خدمة بلوجر من المتغيرات
BLOG_ID = os.getenv("blog_id")
blogger = BloggerService(blog_id=BLOG_ID)

# --- المسارات (Routes) ---


# الصفحة الرئيسية (محمية بكلمة سر)
@app.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    user: str = Depends(authenticate),
    search: str = None,
    cat: str = None,
):
    media_list = SupabaseService.get_media(search_query=search, category=cat)
    return templates.TemplateResponse(
        "index.html", {"request": request, "media_list": media_list, "search": search}
    )


# إضافة عمل جديد
@app.post("/api/media/add")
async def add_new_work(
    user: str = Depends(authenticate),
    title: str = Form(...),
    category: str = Form(...),
    story: str = Form(...),
    year: int = Form(...),
    poster_url: str = Form(...),
):
    payload = {
        "title": title,
        "category": category,
        "story": story,
        "year": year,
        "poster_url": poster_url,
    }
    new_media = SupabaseService.add_media(payload)
    return {"status": "success", "data": new_media}


# تعديل عمل
@app.post("/api/media/update/{media_id}")
async def update_media(
    media_id: int,
    user: str = Depends(authenticate),
    title: str = Form(...),
    story: str = Form(...),
    category: str = Form(...),
    year: int = Form(...),
    poster_url: str = Form(...),
):
    data = {
        "title": title,
        "story": story,
        "category": category,
        "year": year,
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
async def reset_sync(ep_id: int, user: str = Depends(authenticate)):
    try:
        # الحقيقة الصارمة: نستخدم الكلاينت الموجود داخل السيرفيس
        SupabaseService.client.table("episodes").update({"is_synced": False}).eq("id", ep_id).execute()
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

        data = media_res.data
        data["episodes"] = episodes_res.data
        return data
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=7860)
