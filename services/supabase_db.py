from supabase import create_client, Client
import os

# 1. جلب البيانات من متغيرات البيئة (Secrets) التي أنشأتها في Hugging Face
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# 2. إنشاء كائن الاتصال (يجب أن يكون خارج الكلاس ليتم استخدامه في كل الدوال)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

class SupabaseService:
    
    # 1. جلب كل المحتوى مع البحث والفلترة
    @staticmethod
    def get_media(search_query: str = None, category: str = None, only_pending: bool = False):
        query = supabase.table("medias").select("*, episodes(*)")
        
        if search_query:
            query = query.ilike("title", f"%{search_query}%")
        
        if category:
            query = query.eq("category", category)
            
        result = query.order("created_at", desc=True).execute()
        data = result.data

        if only_pending:
            data = [item for item in data if any(not ep['is_synced'] for ep in item['episodes'])]
            
        return data

    # 2. إضافة عمل جديد
    @staticmethod
    def add_media(data: dict):
        result = supabase.table("medias").insert(data).execute()
        return result.data[0] if result.data else None

    # 3. تعديل بيانات عمل موجود
    @staticmethod
    def update_media(media_id: int, data: dict):
        result = supabase.table("medias").update(data).eq("id", media_id).execute()
        return result.data

    # 4. حذف عمل
    @staticmethod
    def delete_media(media_id: int):
        result = supabase.table("medias").delete().eq("id", media_id).execute()
        return result.data

    # 5. إدارة الحلقات
    @staticmethod
    def manage_episode(ep_data: dict, ep_id: int = None):
        if ep_id:
            result = supabase.table("episodes").update(ep_data).eq("id", ep_id).execute()
        else:
            result = supabase.table("episodes").insert(ep_data).execute()
        return result.data