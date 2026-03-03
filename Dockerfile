FROM python:3.11-slim

WORKDIR /code

# التعديل الجوهري: إضافة ffmpeg و unrar و الأداة file للكشف عن نوع الملفات
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    ffmpeg \
    unrar-free \
    file \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1

COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir -r /code/requirements.txt

# تثبيت بيانات NLTK
RUN python -m nltk.downloader punkt punkt_tab

COPY . .

# ضبط الـ CMD ليكون أكثر استقراراً مع العمليات الطويلة
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]