import asyncio
import os

from Bio import Entrez

from agents import emit

Entrez.email = os.environ.get("NCBI_EMAIL", "mediswarm@example.com")
if os.environ.get("NCBI_API_KEY"):
    Entrez.api_key = os.environ.get("NCBI_API_KEY")

AGENT_NAME = "literature_scout"


async def search_pubmed(plan: dict, session_id: str, queue) -> dict:
    await emit(queue, "agent_start", AGENT_NAME, "Connecting to PubMed...")

    search_query = " OR ".join(f'"{t}"' for t in plan["search_terms"])
    search_query += " AND (readmission OR rehospitalization)"

    await emit(queue, "agent_thinking", AGENT_NAME,
               f"Querying PubMed: {search_query[:80]}...")

    # Run Entrez in thread pool to avoid blocking event loop
    loop = asyncio.get_event_loop()

    def _search():
        handle = Entrez.esearch(db="pubmed", term=search_query,
                                retmax=20, sort="relevance",
                                datetype="pdat", reldate=1825)  # last 5 years
        return Entrez.read(handle)

    search_results = await loop.run_in_executor(None, _search)
    ids = search_results["IdList"]

    if not ids:
        raise Exception("No PubMed results found for query")

    await emit(queue, "agent_thinking", AGENT_NAME,
               f"Found {len(ids)} papers. Fetching abstracts...")

    def _fetch():
        handle = Entrez.efetch(db="pubmed", id=ids[:10],
                               rettype="abstract", retmode="xml")
        return Entrez.read(handle)

    records = await loop.run_in_executor(None, _fetch)

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

    await emit(queue, "agent_done", AGENT_NAME,
               f"Retrieved {len(papers)} papers with abstracts",
               {"paper_count": len(papers), "papers": [p["title"] for p in papers[:5]]})

    return {"papers": papers, "search_query": search_query, "total_found": len(ids)}
