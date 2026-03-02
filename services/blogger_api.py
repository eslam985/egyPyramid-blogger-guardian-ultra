import os
import pickle
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import json


class BloggerService:
    def __init__(self, blog_id):
        self.blog_id = blog_id
        self.creds = self._load_credentials()
        self.service = build("blogger", "v3", credentials=self.creds)

    def _load_credentials(self):
        """تحميل التصاريح من السيكرتس مباشرة وتجديدها"""
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request

        # 1. جلب البيانات من Environment Variables (Hugging Face Secrets)
        refresh_token = os.getenv("BLOGGER_REFRESH_TOKEN")
        client_id = os.getenv("CLIENT_ID")  # تأكد أن هذا الاسم مطابق لما في Secrets
        client_secret = os.getenv("CLIENT_SECRET")

        # محاولة بديلة لو البيانات مدمجة في JSON واحد
        if not client_id and os.getenv("GOOGLE_CREDS_JSON"):
            creds_data = json.loads(os.getenv("GOOGLE_CREDS_JSON"))
            # لو هو ملف OAuth Client ID
            if "installed" in creds_data:
                client_id = creds_data["installed"]["client_id"]
                client_secret = creds_data["installed"]["client_secret"]
            # لو هو ملف Service Account (رغم أنه لا يفضل لبلوجر)
            else:
                client_id = creds_data.get("client_id")
                client_secret = creds_data.get("client_secret")

        if not refresh_token or not client_id:
            raise Exception(
                "❌ خطأ: لم يتم العثور على BLOGGER_REFRESH_TOKEN أو CLIENT_ID في السيكرتس"
            )

        # 2. إنشاء كائن التصاريح بدون الحاجة لملفات .pickle أو .json
        creds = Credentials(
            token=None,  # سيتم توليده عند عمل refresh
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=["https://www.googleapis.com/auth/blogger"],
        )

        # 3. تجديد التوكن
        try:
            creds.refresh(Request())
            return creds
        except Exception as e:
            raise Exception(f"❌ فشل تجديد التوكن: {e}")

    def get_service(self):
        """هذه الدالة هي التي تستدعيها في main_publisher.py"""
        return self.service

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
