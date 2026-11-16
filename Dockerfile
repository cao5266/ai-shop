# ---- 阶段 1：构建 React 前端（npm 默认走腾讯云镜像，海外构建可覆盖）
#   docker compose build --build-arg NPM_REGISTRY=https://registry.npmjs.org/
FROM node:22-alpine AS web
WORKDIR /web
ARG NPM_REGISTRY=https://mirrors.cloud.tencent.com/npm/
COPY web/package.json web/package-lock.json web/.npmrc ./
RUN npm ci --no-audit --no-fund --registry "${NPM_REGISTRY}"
COPY web/ ./
RUN npm run build

# ---- 阶段 2：Python 运行时
FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /srv/app
COPY requirements.txt .
# 默认走腾讯云 PyPI 镜像，海外构建可覆盖：
#   docker compose build --build-arg PIP_INDEX_URL=https://pypi.org/simple --build-arg PIP_TRUSTED_HOST=pypi.org
ARG PIP_INDEX_URL=https://mirrors.cloud.tencent.com/pypi/simple
ARG PIP_TRUSTED_HOST=mirrors.cloud.tencent.com
RUN pip install -i "${PIP_INDEX_URL}" --trusted-host "${PIP_TRUSTED_HOST}" -r requirements.txt
COPY backend ./backend
COPY crawler ./crawler
COPY data/seed ./data/seed
COPY --from=web /web/dist ./web/dist
RUN useradd -r -u 10001 app && chown -R app /srv/app
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/healthz')"
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
