"""
Vertex AI Embeddings MCP Tool Server
Provides text embedding capabilities via Vertex AI or sentence-transformers fallback.
"""
import os
from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Vertex AI Embeddings MCP Server")

# Lazy-loaded models
_vertex_model = None
_local_model = None


def _get_embedder():
    """Try Vertex AI first, fall back to local sentence-transformers."""
    global _vertex_model, _local_model

    if _vertex_model is None and _local_model is None:
        project = os.environ.get("GOOGLE_CLOUD_PROJECT")
        region = os.environ.get("GOOGLE_CLOUD_REGION", "asia-southeast1")

        if project:
            try:
                from vertexai.language_models import TextEmbeddingModel
                import vertexai
                vertexai.init(project=project, location=region)
                _vertex_model = TextEmbeddingModel.from_pretrained("text-embedding-004")
                return "vertex", _vertex_model
            except Exception:
                pass

        # Fall back to local model
        try:
            from sentence_transformers import SentenceTransformer
            _local_model = SentenceTransformer("all-MiniLM-L6-v2")
            return "local", _local_model
        except Exception as e:
            raise RuntimeError(f"No embedding model available: {e}")

    if _vertex_model:
        return "vertex", _vertex_model
    return "local", _local_model


class EmbedRequest(BaseModel):
    texts: list[str]
    task_type: str = "RETRIEVAL_DOCUMENT"


class SimilarityRequest(BaseModel):
    query: str
    documents: list[str]
    top_k: int = 5


@app.post("/tools/embed")
def embed_texts(req: EmbedRequest) -> dict:
    """Generate embeddings for a list of texts."""
    try:
        backend, model = _get_embedder()

        if backend == "vertex":
            embeddings = model.get_embeddings(req.texts[:20])
            vectors = [e.values for e in embeddings]
        else:
            vectors = model.encode(req.texts[:20]).tolist()

        return {
            "embeddings": vectors,
            "model": backend,
            "dimension": len(vectors[0]) if vectors else 0
        }
    except Exception as e:
        return {"embeddings": [], "error": str(e)}


@app.post("/tools/semantic_search")
def semantic_search(req: SimilarityRequest) -> dict:
    """Find top-k most relevant documents for a query using cosine similarity."""
    import numpy as np

    try:
        backend, model = _get_embedder()

        all_texts = [req.query] + req.documents
        if backend == "vertex":
            embeddings_obj = model.get_embeddings(all_texts[:21])
            vectors = np.array([e.values for e in embeddings_obj])
        else:
            vectors = model.encode(all_texts[:21])

        query_vec = vectors[0]
        doc_vecs = vectors[1:]

        # Cosine similarity
        norms = np.linalg.norm(doc_vecs, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1, norms)
        doc_vecs_norm = doc_vecs / norms
        query_norm = query_vec / (np.linalg.norm(query_vec) or 1)
        scores = doc_vecs_norm @ query_norm

        top_indices = np.argsort(scores)[::-1][:req.top_k]
        results = [
            {"index": int(i), "text": req.documents[i], "score": float(scores[i])}
            for i in top_indices
        ]
        return {"results": results, "model": backend}
    except Exception as e:
        return {"results": [], "error": str(e)}


@app.get("/tools/list")
def list_tools() -> dict:
    return {
        "tools": [
            {
                "name": "embed",
                "description": "Generate vector embeddings for texts (Vertex AI or local)",
                "parameters": {"texts": "list[string]", "task_type": "string"}
            },
            {
                "name": "semantic_search",
                "description": "Find top-k semantically similar documents",
                "parameters": {"query": "string", "documents": "list[string]", "top_k": "int"}
            }
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
