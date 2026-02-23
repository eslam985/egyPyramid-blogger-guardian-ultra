import os
import pickle
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

class BloggerService:
    def __init__(self, blog_id):
        self.blog_id = blog_id
        self.creds = self._load_credentials()
        self.service = build("blogger", "v3", credentials=self.creds)

    def _load_credentials(self):
        creds = None
        # البحث عن ملف التوكن في المجلد الرئيسي
        token_path = "token.pickle"
        
        if os.path.exists(token_path):
            with open(token_path, "rb") as token:
                creds = pickle.load(token)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                with open(token_path, "wb") as token:
                    pickle.dump(creds, token)
            else:
                # الحقيقة الصارمة: في Docker لا يمكننا فتح متصفح لطلب كود جديد
                raise Exception("❌ توكن بلوجر (token.pickle) غير صالح أو منتهي. قم بتوليده محلياً أولاً.")
        
        return creds

    def get_service(self):
        """هذه الدالة هي التي تستدعيها في main_publisher.py"""
        return self.service

    def change_post_status(self, post_id: str, revert: bool = True):
        try:
            if revert:
                return self.service.posts().revert(blogId=self.blog_id, postId=post_id).execute()
            else:
                return self.service.posts().publish(blogId=self.blog_id, postId=post_id).execute()
        except Exception as e:
            return {"error": str(e)}

    def update_post_content(self, post_id: str, title: str, content: str):
        try:
            body = {"title": title, "content": content}
            return self.service.posts().patch(blogId=self.blog_id, postId=post_id, body=body).execute()
        except Exception as e:
            return {"error": str(e)}
            
    def create_post(self, title, content, is_draft=True):
        """دالة إنشاء مقال جديد التي يستخدمها app.py"""
        try:
            body = {
                "kind": "blogger#post",
                "title": title,
                "content": content
            }
            return self.service.posts().insert(
                blogId=self.blog_id, 
                body=body, 
                isDraft=is_draft
            ).execute()
        except Exception as e:
            return {"error": str(e)}