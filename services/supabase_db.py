import os
from typing import Optional, List, Tuple, Any
from supabase import create_client, Client
from postgrest.exceptions import APIError  # تأكد من إضافة هذا الاستيراد في الأعلى

# جلب القيم وتنظيفها فوراً
RAW_URL = os.getenv("SUPABASE_URL")
RAW_KEY = os.getenv("SUPABASE_KEY")


class SupabaseService:
    client: Optional[Client] = None

    # محاولة إنشاء الكلاينت مرة واحدة فقط بشكل سليم
    if RAW_URL and RAW_KEY:
        try:
            client = create_client(RAW_URL.strip(), RAW_KEY.strip())
            print(
                f"✅ Supabase Initialized. URL: {RAW_URL[:15]}... KEY: {RAW_KEY[:10]}..."
            )
        except Exception as e:
            print(f"❌ Supabase Connection Error: {str(e)}")

    @staticmethod
    def get_media(
        search_query: Optional[str] = None,
        category: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        limit: int = 12,
    ) -> Tuple[List[Any], int]:
        if SupabaseService.client is None:
            return [], 0

        start = (page - 1) * limit
        end = start + limit - 1

        query = SupabaseService.client.table("medias").select(
            "*, episodes(*)", count="exact"
        )

        if search_query:
            query = query.ilike("title", f"%{search_query}%")

        # تصحيح فلتر الفئات (تجاهل 'all')
        if category and category != "all":
            query = query.eq("category", category)

        # --- الحقيقة الصارمة: المعالجة الصحيحة للـ NULL ---
        if status:
            if status == "published":
                query = query.eq("blogger_status", "published")
            elif status == "draft":  # تم تغيير الاسم ليتوافق مع الفرونت إيند
                # استخدام or للبحث عن الـ draft أو الـ NULL
                query = query.or_("blogger_status.neq.published,blogger_status.is.null")

        result = query.order("created_at", desc=True).range(start, end).execute()
        return result.data, (result.count if result.count else 0)

    @staticmethod
    def add_media(data: dict):
        # 1. إدخال الميديا أولاً للحصول على الـ ID
        result = SupabaseService.client.table("medias").insert(data).execute()
        if result.data:
            media = result.data[0]
            m_id = media["id"]
            original_slug = media.get("slug", "")
            
            # 2. تحديث الـ slug ليبدأ بـ ID لضمان توافق Next.js
            if original_slug and not str(original_slug).startswith(f"{m_id}-"):
                new_slug = f"{m_id}-{original_slug}"
                SupabaseService.client.table("medias").update({"slug": new_slug}).eq("id", m_id).execute()
                media["slug"] = new_slug
            
            return media
        return None

    @staticmethod
    def update_media(media_id: int, data: dict):
        try:
            result = (
                SupabaseService.client.table("medias")
                .update(data)
                .eq("id", media_id)
                .execute()
            )
            return result.data
        except APIError as e:
            # كود 23505 هو كود تعارض البيانات (Unique Violation)
            if e.code == "23505":
                print(f"❌ Conflict Error: {e.message}")
                raise Exception(
                    "تعارض في البيانات: يوجد بالفعل عمل بهذا الاسم/السنة أو الـ ID."
                )
            else:
                print(f"❌ Supabase API Error: {e.message}")
                raise e

    @staticmethod
    def delete_media(media_id: int):
        result = (
            SupabaseService.client.table("medias").delete().eq("id", media_id).execute()
        )
        return result.data

    @staticmethod
    def manage_episode(ep_data: dict, ep_id: int = None):
        if ep_id:
            result = (
                SupabaseService.client.table("episodes")
                .update(ep_data)
                .eq("id", ep_id)
                .execute()
            )
        else:
            result = SupabaseService.client.table("episodes").insert(ep_data).execute()
        return result.data
