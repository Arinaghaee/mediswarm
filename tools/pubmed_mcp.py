"""
PubMed MCP Tool Server
Wraps the NCBI Entrez API to provide PubMed search capabilities as an MCP-style tool.
"""
import os
from typing import Optional

from Bio import Entrez
from fastapi import FastAPI
from pydantic import BaseModel

Entrez.email = os.environ.get("NCBI_EMAIL", "mediswarm@example.com")
if os.environ.get("NCBI_API_KEY"):
    Entrez.api_key = os.environ.get("NCBI_API_KEY")

app = FastAPI(title="PubMed MCP Server")


class SearchRequest(BaseModel):
    query: str
    max_results: int = 20
    date_range_days: int = 1825  # 5 years


class FetchRequest(BaseModel):
    pmids: list[str]


@app.post("/tools/pubmed_search")
def pubmed_search(req: SearchRequest) -> dict:
    """Search PubMed for articles matching the query."""
    handle = Entrez.esearch(
        db="pubmed",
        term=req.query,
        retmax=req.max_results,
        sort="relevance",
        datetype="pdat",
        reldate=req.date_range_days
    )
    results = Entrez.read(handle)
    handle.close()
    return {
        "ids": results["IdList"],
        "count": int(results["Count"]),
        "query_translation": results.get("QueryTranslation", "")
    }


@app.post("/tools/pubmed_fetch")
def pubmed_fetch(req: FetchRequest) -> dict:
    """Fetch full abstract data for given PubMed IDs."""
    handle = Entrez.efetch(
        db="pubmed",
        id=req.pmids[:10],
        rettype="abstract",
        retmode="xml"
    )
    records = Entrez.read(handle)
    handle.close()

    papers = []
    for record in records.get("PubmedArticle", []):
        try:
            article = record["MedlineCitation"]["Article"]
            pmid = str(record["MedlineCitation"]["PMID"])
            title = str(article.get("ArticleTitle", ""))

            abstract_text = ""
            if "Abstract" in article:
                abstract_parts = article["Abstract"].get("AbstractText", [])
                if isinstance(abstract_parts, list):
                    abstract_text = " ".join(str(p) for p in abstract_parts)
                else:
                    abstract_text = str(abstract_parts)

            pub_date = article.get("Journal", {}).get("JournalIssue", {}).get("PubDate", {})
            year = str(pub_date.get("Year", ""))

            papers.append({
                "pmid": pmid,
                "title": title,
                "abstract": abstract_text[:1500],
                "year": year,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
            })
        except Exception:
            continue

    return {"papers": papers}


@app.get("/tools/list")
def list_tools() -> dict:
    """List available MCP tools."""
    return {
        "tools": [
            {
                "name": "pubmed_search",
                "description": "Search PubMed for medical literature",
                "parameters": {"query": "string", "max_results": "int", "date_range_days": "int"}
            },
            {
                "name": "pubmed_fetch",
                "description": "Fetch abstracts for given PubMed IDs",
                "parameters": {"pmids": "list[string]"}
            }
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
