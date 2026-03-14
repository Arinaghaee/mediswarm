# SPEC: Deployment (Docker + Cloud Run)

## File: `Dockerfile`

Multi-stage build. Backend serves both the API and the built React app.

```dockerfile
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
```

## Update `main.py` to serve static files

Add after creating the FastAPI app:
```python
from fastapi.staticfiles import StaticFiles
import os

# Serve React build
if os.path.exists("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")
```

Add `aiofiles` to requirements.txt for StaticFiles support.

## File: `cloudbuild.yaml`

```yaml
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', 'gcr.io/$PROJECT_ID/mediswarm', '.']
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'gcr.io/$PROJECT_ID/mediswarm']
  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    entrypoint: gcloud
    args:
      - run
      - deploy
      - mediswarm
      - --image=gcr.io/$PROJECT_ID/mediswarm
      - --region=asia-southeast1
      - --platform=managed
      - --allow-unauthenticated
      - --memory=2Gi
      - --cpu=2
      - --timeout=300
      - --set-env-vars=GOOGLE_CLOUD_PROJECT=$PROJECT_ID
```

## File: `.env.example`

```
GOOGLE_API_KEY=
GOOGLE_CLOUD_PROJECT=
GOOGLE_CLOUD_REGION=asia-southeast1
GCS_BUCKET_NAME=mediswarm-pdf-cache
NCBI_EMAIL=your@email.com
NCBI_API_KEY=
```

## Deployment Steps (run these manually)

```bash
# 1. Authenticate
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# 2. Enable required APIs
gcloud services enable run.googleapis.com cloudbuild.googleapis.com containerregistry.googleapis.com

# 3. Set secrets in Cloud Run (do NOT put in Dockerfile)
gcloud run services update mediswarm \
  --region=asia-southeast1 \
  --set-env-vars="GOOGLE_API_KEY=your_key,NCBI_EMAIL=your@email.com"

# 4. Build and deploy
gcloud builds submit --config cloudbuild.yaml

# 5. Get the URL
gcloud run services describe mediswarm --region=asia-southeast1 --format="value(status.url)"
```

## Local Development

```bash
# Terminal 1 — Backend
pip install -r requirements.txt
cp .env.example .env
# Fill in .env values
uvicorn main:app --reload --port 8000

# Terminal 2 — Frontend
cd app
npm install
npm run dev
# Proxies /api to localhost:8000
```
