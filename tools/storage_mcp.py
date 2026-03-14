"""
Google Cloud Storage MCP Tool Server
Provides PDF caching capabilities backed by GCS.
"""
import io
import os
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Storage MCP Server")

GCS_BUCKET = os.environ.get("GCS_BUCKET_NAME", "mediswarm-pdf-cache")

# Lazy-load GCS client only when credentials are available
_gcs_client = None
_bucket = None


def _get_bucket():
    global _gcs_client, _bucket
    if _bucket is None:
        try:
            from google.cloud import storage
            _gcs_client = storage.Client(project=os.environ.get("GOOGLE_CLOUD_PROJECT"))
            _bucket = _gcs_client.bucket(GCS_BUCKET)
        except Exception as e:
            raise RuntimeError(f"GCS not available: {e}")
    return _bucket


class StoreRequest(BaseModel):
    key: str
    content: str  # base64 encoded or plain text


class RetrieveRequest(BaseModel):
    key: str


@app.post("/tools/store_pdf_text")
def store_pdf_text(req: StoreRequest) -> dict:
    """Cache PDF text content in GCS."""
    try:
        bucket = _get_bucket()
        blob = bucket.blob(f"pdf_cache/{req.key}")
        blob.upload_from_string(req.content, content_type="text/plain")
        return {"status": "stored", "key": req.key, "bucket": GCS_BUCKET}
    except Exception as e:
        return {"status": "error", "message": str(e), "fallback": "local"}


@app.post("/tools/retrieve_pdf_text")
def retrieve_pdf_text(req: RetrieveRequest) -> dict:
    """Retrieve cached PDF text from GCS."""
    try:
        bucket = _get_bucket()
        blob = bucket.blob(f"pdf_cache/{req.key}")
        if not blob.exists():
            raise HTTPException(status_code=404, detail="PDF not found in cache")
        content = blob.download_as_text()
        return {"status": "found", "key": req.key, "content": content}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/list_cached")
def list_cached() -> dict:
    """List all cached PDFs."""
    try:
        bucket = _get_bucket()
        blobs = list(bucket.list_blobs(prefix="pdf_cache/"))
        return {"cached_keys": [b.name.replace("pdf_cache/", "") for b in blobs]}
    except Exception as e:
        return {"cached_keys": [], "error": str(e)}


@app.get("/tools/list")
def list_tools() -> dict:
    return {
        "tools": [
            {
                "name": "store_pdf_text",
                "description": "Cache extracted PDF text in Google Cloud Storage",
                "parameters": {"key": "string", "content": "string"}
            },
            {
                "name": "retrieve_pdf_text",
                "description": "Retrieve cached PDF text from GCS",
                "parameters": {"key": "string"}
            },
            {
                "name": "list_cached",
                "description": "List all cached PDF keys",
                "parameters": {}
            }
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
