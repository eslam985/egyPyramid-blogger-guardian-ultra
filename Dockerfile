FROM python:3.11-slim

WORKDIR /code

# 1. تثبيت الحزم (بصلاحيات root)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc python3-dev ffmpeg unrar-free file nodejs npm \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# 2. نسخ ملفات المشروع الضرورية للـ Build
# ننسخ الملفات التي يحتاجها Vite ليتمكن من رؤية index.html و vite.config.js
COPY package*.json vite.config.js index.html ./
COPY src/ ./src/

# 3. تنفيذ الـ Build
RUN npm install && npm run build

# 4. إنشاء المستخدم وإعطاؤه ملكية المجلد بالكامل
RUN useradd -m -u 1000 user && chown -R user:user /code
USER user
ENV PATH="/home/user/.local/bin:${PATH}"

# 5. نسخ باقي الملفات (بصلاحيات user)
COPY --chown=user:user . .

# 6. تثبيت متطلبات Python
RUN pip install --no-cache-dir --user -r requirements.txt
RUN python -m nltk.downloader punkt punkt_tab

EXPOSE 7860
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]