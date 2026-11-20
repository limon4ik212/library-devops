# ---------- Этап 1: сборка зависимостей ----------
FROM python:3.12-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---------- Этап 2: финальный образ ----------
FROM python:3.12-slim

LABEL org.opencontainers.image.title="library-is" \
      org.opencontainers.image.description="Информационная система управления библиотекой (СРО №15)"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

# Непривилегированный пользователь
RUN groupadd --system app && useradd --system --gid app --no-create-home app

WORKDIR /srv
COPY --from=builder /install /usr/local
COPY --chown=app:app app ./app

USER app
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health', timeout=2).status==200 else 1)"

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--access-logfile", "-", "app.wsgi:app"]
