FROM python:3.11-slim

WORKDIR /code

# 1. تثبيت الحزم الأساسية (أضفنا build-essential للتعامل مع المكتبات الأصلية مثل tailwind)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ make python3-dev ffmpeg unrar-free file nodejs npm \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# 2. نسخ ملفات الـ JS فقط أولاً (لتحسين الـ Layer Caching)
COPY package*.json ./
# مسح الـ modules القديمة إن وجدت وضمان بيئة نظيفة
RUN rm -rf node_modules && npm install

# 3. نسخ باقي الكود
COPY . .

# 4. بناء الفرونت إيند
RUN npm run build

# 5. إعداد المستخدم والبيئة
RUN useradd -m -u 1000 user
RUN chown -R user:user /code/static/dist

USER user
ENV PATH="/home/user/.local/bin:${PATH}"

# 6. تثبيت مكتبات بايثون
RUN pip install --no-cache-dir --user -r requirements.txt
RUN python -m nltk.downloader punkt punkt_tab

EXPOSE 7860
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]