FROM python:3.11-slim

WORKDIR /code

# فقط انسخ ملف المتطلبات وثبت المكتبات
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# انسخ الكود الخاص بك
COPY . .

EXPOSE 7860

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]