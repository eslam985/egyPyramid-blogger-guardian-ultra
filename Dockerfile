    FROM python:3.11-slim

    WORKDIR /code

    # تثبيت التبعيات الضرورية فقط وبأقل حجم
    RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc python3-dev && \
        apt-get clean && rm -rf /var/lib/apt/lists/*

    COPY ./requirements.txt /code/requirements.txt
    RUN pip install --no-cache-dir -r /code/requirements.txt

    COPY . .

    # زيادة مدة الـ Timeout وتقليل الـ Workers لأقصى درجة
    CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1", "--timeout-keep-alive", "30"]