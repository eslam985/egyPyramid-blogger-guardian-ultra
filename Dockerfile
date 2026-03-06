FROM python:3.11-slim

WORKDIR /code

# 1. تثبيت الحزم
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc python3-dev ffmpeg unrar-free file nodejs npm \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# 2. نسخ الكود وبناء الفرونت إيند
COPY . .
RUN npm install && npm run build

# 3. إعداد المستخدم والبيئة
RUN useradd -m -u 1000 user
# تغيير ملكية مجلد الـ build قبل التحول للمستخدم
RUN chown -R user:user /code/static/dist

USER user
ENV PATH="/home/user/.local/bin:${PATH}"

# 4. تثبيت مكتبات بايثون
RUN pip install --no-cache-dir --user -r requirements.txt
RUN python -m nltk.downloader punkt punkt_tab

EXPOSE 7860
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]