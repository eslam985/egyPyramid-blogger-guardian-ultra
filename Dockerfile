# استخدم نسخة بايثون الكاملة لضمان استقرار المكتبات
FROM python:3.11-slim

# 1. تثبيت أدوات النظام (إضافة wget لتحميل ملفات IMDb وتور للبروكسي)
RUN apt-get update && apt-get install -y \
    fonts-liberation \
    ffmpeg \
    curl \
    wget \
    gnupg \
    p7zip-full \
    unzip \
    ca-certificates \
    tor \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# إعطاء صلاحيات الكتابة لمسارات Tor حتى يعمل بدون مشاكل مع مستخدم Hugging Face (الذي لا يملك صلاحيات Root كاملة)
RUN mkdir -p /var/run/tor /var/lib/tor /var/log/tor && \
    chmod -R 777 /var/run/tor /var/lib/tor /var/log/tor /etc/tor

WORKDIR /app

# 2. تحديث pip ونسخ المتطلبات
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 3. تثبيت متصفح Chromium وتعريفاته (مهم جداً للـ Mixdrop و Playwright)
RUN playwright install chromium
RUN playwright install-deps chromium
# --- مرحلة بناء الرادار المحلي (IMDb Index) ---
# تحميل الملفات وتصفيتها لتقليل الحجم (سنة 2010+)
RUN wget https://datasets.imdbws.com/title.basics.tsv.gz \
    && wget https://datasets.imdbws.com/title.ratings.tsv.gz \
    && mkdir -p downloader_new/metadata

# نسخ سكريبت البناء فقط لتشغيله
COPY scripts/build_local_db.py ./scripts/build_local_db.py
RUN python3 scripts/build_local_db.py \
    && rm title.basics.tsv.gz title.ratings.tsv.gz
# --------------------------------------------
# 4. نسخ كل ملفات المشروع
COPY . .

# 5. تجهيز الخط (arial.ttf) كما كنت تفعل في كولاب
# هننقل الخط لمجلد العمل عشان كود المعالجة يلاقيه
RUN cp /usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf /app/arial.ttf

# 6. صلاحيات المستخدم (Hugging Face بيطلب صلاحيات معينة أحياناً)
RUN chmod -R 777 /app

EXPOSE 7860

# 7. التشغيل (تشغيل Tor في الخلفية، يليه تشغيل تطبيق FastAPI)
# ملاحظة: في الخطوة الجاية هعلمك إزاي تخلي الـ app.py يشغل الـ Worker في الخلفية
CMD ["sh", "-c", "tor & uvicorn app:app --host 0.0.0.0 --port 7860"]