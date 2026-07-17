FROM python:3.12-slim

ARG USE_CN_MIRROR=false
ARG PIP_INDEX_URL=https://pypi.org/simple

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN if [ "$USE_CN_MIRROR" = "true" ]; then \
        sed -i 's|deb.debian.org|mirrors.aliyun.com|g; s|security.debian.org|mirrors.aliyun.com/debian-security|g' \
        /etc/apt/sources.list.d/debian.sources; \
    fi \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 libgomp1 poppler-utils \
        tesseract-ocr tesseract-ocr-chi-sim fonts-noto-cjk \
        libreoffice-core libreoffice-writer libreoffice-impress libreoffice-java-common \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip -i ${PIP_INDEX_URL} \
    && pip install -r requirements.txt -i ${PIP_INDEX_URL}

COPY app ./app

EXPOSE 18000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "18000", "--proxy-headers", "--forwarded-allow-ips", "*"]