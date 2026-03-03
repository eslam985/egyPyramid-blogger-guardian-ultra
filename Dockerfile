FROM python:3.11-slim

WORKDIR /code

# إبقاء الأدوات الأساسية فقط لتقليل حجم الصورة وسرعة التشغيل
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    ffmpeg \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1

# نسخ وتثبيت المكتبات الأساسية
COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir -r /code/requirements.txt

# --- [تم حذف سطر NLTK لأنه سيسبب فشل الآن] ---

COPY . .

# تشغيل السيرفر
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]