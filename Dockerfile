FROM node:22-bookworm-slim AS web
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
ENV VITE_API_BASE_URL=/
RUN npm run build

FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 TRIP_FAST_MODE=true
WORKDIR /app/backend
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
ENV UV_TOOL_DIR=/opt/amap-tools UV_TOOL_BIN_DIR=/usr/local/bin
RUN uv tool install --with pydantic==2.10.6 --with pydantic-settings==2.8.1 amap-mcp-server==0.1.11
COPY backend/app ./app
COPY backend/cloud_app.py ./cloud_app.py
COPY --from=web /build/dist /app/frontend/dist
EXPOSE 10000
CMD ["sh", "-c", "exec uvicorn cloud_app:app --host 0.0.0.0 --port ${PORT:-10000}"]
