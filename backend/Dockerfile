FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/ \
    PIP_TRUSTED_HOST=mirrors.aliyun.com

WORKDIR /app

RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g; s|security.debian.org|mirrors.aliyun.com/debian-security|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
        poppler-utils \
        tesseract-ocr \
        tesseract-ocr-chi-sim \
        fonts-noto-cjk \
        libreoffice-core \
        libreoffice-writer \
        libreoffice-impress \
        libreoffice-java-common \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY app ./app

EXPOSE 18000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "18000", "--proxy-headers", "--forwarded-allow-ips", "*"]
