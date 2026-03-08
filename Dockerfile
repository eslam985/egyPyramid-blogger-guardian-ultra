FROM python:3.11-slim

WORKDIR /code

# تحديث وتثبيت الأدوات الأساسية فقط
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ make python3-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# تثبيت المكتبات (بدون --user، تثبيت عام للنظام داخل الحاوية)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# انسخ باقي الكود
COPY . .

# لا حاجة لإنشاء user جديد ولا تغيير ملكية الملفات
# ولا حاجة لـ ENV PATH المعقدة

EXPOSE 7860

# تشغيل الـ uvicorn مباشرة
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]