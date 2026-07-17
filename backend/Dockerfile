FROM python:3.12-slim-bookworm

ARG USE_CN_MIRROR=true
ARG APT_MIRROR=mirrors.aliyun.com
ARG PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
ARG INSTALL_CJK_FONTS=false

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN if [ "$USE_CN_MIRROR" = "true" ]; then \
        sed -i "s|deb.debian.org|${APT_MIRROR}|g; s|security.debian.org|${APT_MIRROR}|g" /etc/apt/sources.list.d/debian.sources; \
    fi \
    && apt-get -o Acquire::Retries=5 -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30 update \
    && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 libgomp1 poppler-utils \
        tesseract-ocr tesseract-ocr-chi-sim \
        libreoffice-core libreoffice-writer libreoffice-impress \
    && if [ "$INSTALL_CJK_FONTS" = "true" ]; then \
        apt-get install -y --no-install-recommends fonts-noto-cjk; \
    fi \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip -i ${PIP_INDEX_URL} \
    && pip install --no-cache-dir -r requirements.txt -i ${PIP_INDEX_URL}

COPY app ./app

EXPOSE 18000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "18000", "--proxy-headers", "--forwarded-allow-ips", "*"]
