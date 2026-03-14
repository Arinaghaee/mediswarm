FROM node:20-slim AS frontend-build
WORKDIR /app/frontend
COPY app/package*.json ./
RUN npm ci
COPY app/ .
RUN npm run build

FROM python:3.11-slim AS backend
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY agents/ ./agents/
COPY tools/ ./tools/
COPY main.py .

COPY --from=frontend-build /app/frontend/dist ./static

ENV PORT=8080
EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
