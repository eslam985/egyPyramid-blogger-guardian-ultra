FROM python:3.11-slim

WORKDIR /code

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    ffmpeg \
    unrar-free \
    file \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1

# إضافة مستخدم غير root
RUN useradd -m -u 1000 user
# ... (نفس البداية) ...
USER user
ENV PATH="/home/user/.local/bin:${PATH}"

# أضف تثبيت Node.js لبناء الـ Vue
RUN apt-get update && apt-get install -y nodejs npm && apt-get clean

COPY --chown=user . .

# بناء الـ Vue
RUN npm install && npm run build

# تثبيت متطلبات Python
RUN pip install --no-cache-dir --user -r /code/requirements.txt

EXPOSE 7860
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]