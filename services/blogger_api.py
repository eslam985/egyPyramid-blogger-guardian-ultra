import os
import pickle
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import json
import httplib2


class BloggerService:
    def __init__(self, blog_id):
        self.blog_id = blog_id
        # لم نعد نخزن self.service هنا، لأن الخدمة يجب أن تُبنى ديناميكياً

    def _load_credentials(self):
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request

        client_id = os.getenv("CLIENT_ID")
        client_secret = os.getenv("CLIENT_SECRET")
        refresh_token = os.getenv("BLOGGER_REFRESH_TOKEN")

        print(f"DEBUG: Token loaded? {bool(refresh_token)}")
        if not refresh_token:
            raise Exception("❌ BLOGGER_REFRESH_TOKEN غير موجود في البيئة!")

        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=["https://www.googleapis.com/auth/blogger"],
        )

        try:
            # تجديد التوكن فوراً قبل إرجاع الاعتمادات
            creds.refresh(Request())
            return creds
        except Exception as e:
            raise Exception(f"❌ فشل تجديد التوكن: {e}")

    def get_service(self):
        """بناء الخدمة في اللحظة التي يتم استدعاؤها فيها لضمان حداثة الـ Credentials"""
        creds = self._load_credentials()
        return build("blogger", "v3", credentials=creds)

    def change_post_status(self, post_id: str, revert: bool = True):
        try:
            if revert:
                return (
                    self.service.posts()
                    .revert(blogId=self.blog_id, postId=post_id)
                    .execute()
                )
            else:
                return (
                    self.service.posts()
                    .publish(blogId=self.blog_id, postId=post_id)
                    .execute()
                )
        except Exception as e:
            return {"error": str(e)}

    def update_post_content(self, post_id: str, title: str, content: str):
        try:
            body = {"title": title, "content": content}
            return (
                self.service.posts()
                .patch(blogId=self.blog_id, postId=post_id, body=body)
                .execute()
            )
        except Exception as e:
            return {"error": str(e)}

    def create_post(self, title, content, is_draft=True):
        """دالة إنشاء مقال جديد التي يستخدمها app.py"""
        try:
            body = {"kind": "blogger#post", "title": title, "content": content}
            return (
                self.service.posts()
                .insert(blogId=self.blog_id, body=body, isDraft=is_draft)
                .execute()
            )
        except Exception as e:
            return {"error": str(e)}
