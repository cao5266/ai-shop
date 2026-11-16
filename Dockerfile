FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /srv/app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY backend ./backend
COPY static ./static
COPY data/seed ./data/seed
RUN useradd -r -u 10001 app && chown -R app /srv/app
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/healthz')"
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
