FROM python:3.11-slim

WORKDIR /code

# 1. تثبيت الحزم (بصلاحيات root)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc python3-dev ffmpeg unrar-free file nodejs npm \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# 2. نسخ ملفات الـ JS وتنفيذ الـ Build (بصلاحيات root لضمان عدم وجود مشاكل صلاحيات)
COPY package*.json ./
RUN npm install && npm run build

# 3. إنشاء المستخدم وإعطاؤه ملكية المجلد بالكامل
RUN useradd -m -u 1000 user && chown -R user:user /code
USER user
ENV PATH="/home/user/.local/bin:${PATH}"

# 4. نسخ باقي الملفات (بصلاحيات user)
COPY --chown=user:user . .

# 5. تثبيت متطلبات Python
RUN pip install --no-cache-dir --user -r requirements.txt
RUN python -m nltk.downloader punkt punkt_tab

EXPOSE 7860
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]