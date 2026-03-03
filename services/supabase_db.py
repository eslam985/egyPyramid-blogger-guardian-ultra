from supabase import create_client, Client
import os

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


class SupabaseService:
    # الحقيقة الصارمة: لا تنشئ الكلاينت إلا إذا كانت المفاتيح موجودة فعلاً
    client: Client = None
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            client = create_client(SUPABASE_URL, SUPABASE_KEY)
        except Exception as e:
            print(f"❌ Critical: Supabase Init Failed: {e}")

    @staticmethod
    def get_media(
        search_query: str = None, category: str = None, only_pending: bool = False
    ):
        # نستخدم SupabaseService.client دائماً
        query = SupabaseService.client.table("medias").select("*, episodes(*)")

        if search_query:
            query = query.ilike("title", f"%{search_query}%")

        if category:
            query = query.eq("category", category)

        result = query.order("created_at", desc=True).execute()
        data = result.data

        if only_pending:
            data = [
                item
                for item in data
                if any(not ep["is_synced"] for ep in item["episodes"])
            ]

        return data

    @staticmethod
    def add_media(data: dict):
        result = SupabaseService.client.table("medias").insert(data).execute()
        return result.data[0] if result.data else None

    @staticmethod
    def update_media(media_id: int, data: dict):
        result = (
            SupabaseService.client.table("medias")
            .update(data)
            .eq("id", media_id)
            .execute()
        )
        return result.data

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
