# استخدم نسخة بايثون الكاملة لضمان استقرار المكتبات
FROM python:3.11-slim

# جعل مخرجات بايثون تظهر فوراً في الـ Logs بدون تخزين مؤقت
ENV PYTHONUNBUFFERED=1
# 1. تثبيت أدوات النظام (إضافة wget لتحميل ملفات IMDb)
RUN apt-get update && apt-get install -y \
    fonts-liberation \
    ffmpeg \
    curl \
    wget \
    gnupg \
    p7zip-full \
    unzip \
    ca-certificates \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2. تحديث pip ونسخ المتطلبات
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 3. تثبيت متصفح Chromium وتعريفاته (مهم جداً للـ Mixdrop و Playwright)
RUN playwright install chromium
RUN playwright install-deps chromium

# 4. نسخ كل ملفات المشروع
COPY . .

# 5. تجهيز الخط (arial.ttf) كما كنت تفعل في كولاب
# هننقل الخط لمجلد العمل عشان كود المعالجة يلاقيه
RUN cp /usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf /app/arial.ttf

# 6. صلاحيات المستخدم (Hugging Face بيطلب صلاحيات معينة أحياناً)
RUN chmod -R 777 /app

EXPOSE 7860

# 7. التشغيل (هنا هنشغل الـ FastAPI)
# ملاحظة: في الخطوة الجاية هعلمك إزاي تخلي الـ app.py يشغل الـ Worker في الخلفية
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]