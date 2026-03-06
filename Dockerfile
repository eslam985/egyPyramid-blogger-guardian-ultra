FROM python:3.11-slim

WORKDIR /code

# 1. تثبيت الحزم (بصلاحيات root)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc python3-dev ffmpeg unrar-free file nodejs npm \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# 2. نسخ كل ملفات المشروع دفعة واحدة (بدل التقسيم)
COPY . .

# 3. تثبيت متطلبات Node وبناء المشروع
RUN npm install && npm run build

# 4. تثبيت متطلبات Python
RUN pip install --no-cache-dir --user -r requirements.txt
RUN python -m nltk.downloader punkt punkt_tab

# 5. إنشاء المستخدم وتغيير ملكية كل شيء (بما في ذلك الـ build الناتج)
RUN useradd -m -u 1000 user && chown -R user:user /code
USER user
ENV PATH="/home/user/.local/bin:${PATH}"

EXPOSE 7860
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]