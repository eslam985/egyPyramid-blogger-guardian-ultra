from googleapiclient.discovery import build
from google.oauth2 import service_account
import json
import os

class BloggerService:
    def __init__(self, blog_id):
        self.blog_id = blog_id
        # قراءة محتوى الـ JSON من متغيرات البيئة (Secrets)
        creds_json = os.getenv("GOOGLE_CREDS_JSON")
        
        if not creds_json:
            raise ValueError("❌ خطأ: لم يتم العثور على GOOGLE_CREDS_JSON في الإعدادات")
            
        try:
            info = json.loads(creds_json)
            self.creds = service_account.Credentials.from_service_account_info(
                info, scopes=['https://www.googleapis.com/auth/blogger']
            )
            self.service = build('blogger', 'v3', credentials=self.creds)
        except Exception as e:
            raise Exception(f"❌ فشل في تحليل بيانات Google Credentials: {str(e)}")

    # 1. تحويل المقال لمسودة (Draft) أو نشر (Live)
    def change_post_status(self, post_id: str, revert: bool = True):
        try:
            if revert:
                request = self.service.posts().revert(blogId=self.blog_id, postId=post_id)
            else:
                request = self.service.posts().publish(blogId=self.blog_id, postId=post_id)
            return request.execute()
        except Exception as e:
            return {"error": str(e)}

    # 2. تحديث محتوى المقال يدوياً
    def update_post_content(self, post_id: str, title: str, content: str):
        try:
            body = {
                "title": title,
                "content": content
            }
            request = self.service.posts().patch(blogId=self.blog_id, postId=post_id, body=body)
            return request.execute()
        except Exception as e:
            return {"error": str(e)}