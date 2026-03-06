FROM python:3.11-slim

WORKDIR /code

# 1. تثبيت كل المتطلبات (System dependencies) بصلاحيات Root
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    ffmpeg \
    unrar-free \
    file \
    nodejs \
    npm \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1

# 2. إنشاء المستخدم وتغيير الملكية للملفات لاحقاً
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:${PATH}"

# 3. بناء الفرونت إيند
COPY --chown=user:user . .
RUN npm install && npm run build

# 4. تثبيت متطلبات Python
RUN pip install --no-cache-dir --user -r requirements.txt

# 5. التجهيز النهائي
RUN python -m nltk.downloader punkt punkt_tab

EXPOSE 7860
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]