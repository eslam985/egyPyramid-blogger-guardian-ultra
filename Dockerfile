# 1. المرحلة الأولى: بناء الـ Frontend (Node.js)
FROM node:18-slim AS builder
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

# 2. المرحلة النهائية: تشغيل التطبيق (Python)
FROM python:3.11-slim
WORKDIR /code

# تثبيت الحزم الأساسية للنظام
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc python3-dev ffmpeg unrar-free file \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# تثبيت مكتبات بايثون أولاً (هذه الطبقة سيتم تخزينها مؤقتاً ولن يعاد بناؤها إلا إذا تغير ملف requirements.txt)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    python -m nltk.downloader punkt punkt_tab

# نسخ ملفات الـ build من مرحلة الـ node
COPY --from=builder /app/static/dist /code/static/dist

# نسخ باقي الكود (هذه الطبقة تتغير كثيراً، لذا نضعها في النهاية)
COPY . .

RUN useradd -m -u 1000 user && chown -R user:user /code
USER user

EXPOSE 7860
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]