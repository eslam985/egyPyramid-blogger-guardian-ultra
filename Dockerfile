# 1. المرحلة الأولى: بناء الـ Frontend
FROM node:18-slim AS builder
WORKDIR /app

# تثبيت المكتبات اللازمة للبناء
RUN apt-get update && apt-get install -y python3 make g++

COPY package*.json ./
# إعادة بناء المكتبات الأصلية لضمان التوافق
RUN npm install --build-from-source
COPY . .
RUN npm run build

# 2. المرحلة النهائية
FROM python:3.11-slim
WORKDIR /code

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc python3-dev ffmpeg unrar-free file \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    python -m nltk.downloader punkt punkt_tab

# نسخ الـ build
COPY --from=builder /app/static/dist /code/static/dist
COPY . .

RUN useradd -m -u 1000 user && chown -R user:user /code
USER user

EXPOSE 7860
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]