FROM python:3.11-slim

WORKDIR /code

# تثبيت التبعيات الضرورية
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc python3-dev && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# إيقاف تخزين المخرجات مؤقتاً لضمان ظهور الـ Logs في Hugging Face فوراً
ENV PYTHONUNBUFFERED=1

COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir -r /code/requirements.txt

# تحميل بيانات NLTK (مهم جداً لمكتبة TextBlob المستخدمة في utils)
RUN python -m nltk.downloader punkt punkt_tab

COPY . .

# التعديل: زيادة مدة الـ Timeout لأن عمليات الـ AI والنشر تأخذ وقتاً
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1", "--timeout-keep-alive", "60"]