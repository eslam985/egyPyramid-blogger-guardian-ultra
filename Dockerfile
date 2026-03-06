FROM python:3.11-slim

WORKDIR /code

# 1. تثبيت الحزم (root)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc python3-dev ffmpeg unrar-free file nodejs npm \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# 2. بناء الفرونت إيند
COPY . .
RUN npm install && npm run build

# 3. إعداد المستخدم والـ PATH
RUN useradd -m -u 1000 user
USER user
# إضافة المسار هنا مهم جداً ليتمكن المستخدم من رؤية uvicorn
ENV PATH="/home/user/.local/bin:${PATH}"

# 4. تثبيت متطلبات Python (بعد أن أصبحنا مستخدم user)
RUN pip install --no-cache-dir --user -r requirements.txt
RUN python -m nltk.downloader punkt punkt_tab

# 5. تغيير الملكية للملفات المتبقية (يجب أن يتم كـ root قبل التحول للمستخدم)
# يمكنك تنفيذ هذا الجزء قبل تغيير المستخدم USER user
EXPOSE 7860
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]