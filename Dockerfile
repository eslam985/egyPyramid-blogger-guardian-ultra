FROM python:3.11-slim

WORKDIR /code

# إزالة الأدوات غير الضرورية لتسريع البناء
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ make python3-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# تثبيت المكتبات (بعد تنظيف requirements.txt)
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# انسخ الكود والملفات الثابتة الجاهزة (بدل البناء داخل الـ Docker)
COPY . .

# لا تقم بـ npm install هنا إذا كنت ترفع الـ dist جاهزاً من جهازك!
# إذا كنت ترفع الـ dist، احذف أسطر الـ nodejs والـ npm تماماً لتسريع الـ Build 10 مرات.

RUN useradd -m -u 1000 user && \
    chown -R user:user /code

USER user
ENV PATH="/home/user/.local/bin:${PATH}"

EXPOSE 7860
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]