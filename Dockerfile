FROM python:3.11-slim

WORKDIR /code

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ make python3-dev ffmpeg unrar-free file nodejs npm \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY package*.json ./
RUN npm install

# انسخ باقي الكود *قبل* البناء
COPY . .
RUN npm run build

# تأكد من إنشاء المجلد قبل تغيير ملكيته
RUN mkdir -p /code/static/dist && \
    useradd -m -u 1000 user && \
    chown -R user:user /code

USER user
ENV PATH="/home/user/.local/bin:${PATH}"

RUN pip install --no-cache-dir --user -r requirements.txt
RUN python -m nltk.downloader punkt punkt_tab

EXPOSE 7860
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]