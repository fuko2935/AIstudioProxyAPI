# Dockerfile

#ARG PROXY_ADDR="http://host.docker.internal:7890" Not: Linux'ta host.docker.internal sorun oluşturabilir, gerçek proxy adresini kullanın
FROM python:3.10-slim-bookworm AS builder

ARG DEBIAN_FRONTEND=noninteractive
ARG PROXY_ADDR

RUN if [ -n "$PROXY_ADDR" ]; then \
    printf 'Acquire::http::Proxy "%s";\nAcquire::https::Proxy "%s";\n' "$PROXY_ADDR" "$PROXY_ADDR" > /etc/apt/apt.conf.d/99proxy; \
    fi && \
    apt-get update && \
    apt-get install -y --no-install-recommends curl \
    && apt-get clean && rm -rf /var/lib/apt/lists/* && \
    if [ -n "$PROXY_ADDR" ]; then rm -f /etc/apt/apt.conf.d/99proxy; fi

ENV HTTP_PROXY=${PROXY_ADDR}
ENV HTTPS_PROXY=${PROXY_ADDR}

ENV POETRY_HOME="/opt/poetry"
ENV POETRY_VERSION=1.8.3
RUN curl -sSL https://install.python-poetry.org | python3 - --version ${POETRY_VERSION}
ENV PATH="${POETRY_HOME}/bin:${PATH}"

WORKDIR /app_builder
COPY pyproject.toml poetry.lock ./
RUN poetry config virtualenvs.create false --local && \
    poetry install --no-root --no-dev --no-interaction --no-ansi

FROM python:3.10-slim-bookworm

ARG DEBIAN_FRONTEND=noninteractive
ARG PROXY_ADDR

ENV HTTP_PROXY=${PROXY_ADDR}
ENV HTTPS_PROXY=${PROXY_ADDR}

# Adım 1: Tüm sistem bağımlılıklarını kur
# Playwright ihtiyaçları da bu bölümde kuruluyor
RUN \
    if [ -n "$PROXY_ADDR" ]; then \
    printf 'Acquire::http::Proxy "%s";\nAcquire::https::Proxy "%s";\n' "$PROXY_ADDR" "$PROXY_ADDR" > /etc/apt/apt.conf.d/99proxy; \
    fi && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    libatk1.0-0 libatk-bridge2.0-0 libcups2 libdbus-1-3 libdrm2 libgbm1 libgtk-3-0 libnspr4 libnss3 libx11-6 libx11-xcb1 libxcb1 libxcomposite1 libxdamage1 libxext6 libxfixes3 libxrandr2 libxrender1 libxtst6 ca-certificates fonts-liberation libasound2 libpangocairo-1.0-0 libpango-1.0-0 libu2f-udev \
    supervisor curl \
    && \
    # Temizlik işlemleri
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    if [ -n "$PROXY_ADDR" ]; then rm -f /etc/apt/apt.conf.d/99proxy; fi

RUN groupadd -r appgroup && useradd -r -g appgroup -s /bin/bash -d /app appuser

WORKDIR /app

# Adım 2: Python paketlerini ve yürütülebilir dosyaları kopyala
# Playwright kullanılmadan önce bu adımın tamamlanması önemlidir
COPY --from=builder /usr/local/lib/python3.10/site-packages/ /usr/local/lib/python3.10/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/
COPY --from=builder /opt/poetry/bin/poetry /usr/local/bin/poetry

# Uygulama kodunu kopyala
COPY . .

# Adım 3: Python modülleri hazır, komutlar güvenle çalıştırılabilir
# Not: `playwright install-deps` gerekmez; bağımlılıklar yukarıda yüklendi
RUN camoufox fetch && \
    python -m playwright install firefox

# Klasörleri oluştur ve izinleri ayarla
RUN mkdir -p /app/logs && \
    mkdir -p /app/auth_profiles/active && \
    mkdir -p /app/auth_profiles/saved && \
    mkdir -p /app/certs && \
    mkdir -p /app/browser_utils/custom_scripts && \
    mkdir -p /home/appuser/.cache/ms-playwright && \
    mkdir -p /home/appuser/.mozilla && \
    chown -R appuser:appgroup /app && \
    chown -R appuser:appgroup /home/appuser

COPY supervisord.conf /etc/supervisor/conf.d/app.conf

# Camoufox önbellek mantığını düzelt
RUN mkdir -p /var/cache/camoufox && \
    if [ -d /root/.cache/camoufox ]; then cp -a /root/.cache/camoufox/* /var/cache/camoufox/; fi && \
    mkdir -p /app/.cache && \
    ln -s /var/cache/camoufox /app/.cache/camoufox

RUN python update_browserforge_data.py

# Proxy ortam değişkenlerini temizle
ENV HTTP_PROXY=""
ENV HTTPS_PROXY=""

EXPOSE 2048
EXPOSE 3120

USER appuser
ENV HOME=/app
ENV PLAYWRIGHT_BROWSERS_PATH=/home/appuser/.cache/ms-playwright

ENV PYTHONUNBUFFERED=1

ENV PORT=8000
ENV DEFAULT_FASTAPI_PORT=2048
ENV DEFAULT_CAMOUFOX_PORT=9222
ENV STREAM_PORT=3120
ENV SERVER_LOG_LEVEL=INFO
ENV DEBUG_LOGS_ENABLED=false
ENV AUTO_CONFIRM_LOGIN=true
ENV SERVER_PORT=2048
ENV INTERNAL_CAMOUFOX_PROXY=""

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/app.conf"]
