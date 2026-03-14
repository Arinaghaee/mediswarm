import asyncio
import logging
import os

from Bio import Entrez

from agents import emit

logger = logging.getLogger(__name__)
AGENT_NAME = "literature_scout"


def _ensure_email():
    """Guarantee a valid email is set — PubMed rejects requests without one."""
    if not Entrez.email or Entrez.email == "mediswarm@example.com":
        Entrez.email = os.environ.get("NCBI_EMAIL", "test@test.com")
    if os.environ.get("NCBI_API_KEY"):
        Entrez.api_key = os.environ.get("NCBI_API_KEY")
    logger.debug("[%s] Entrez configured | email=%r | api_key_set=%s",
                 AGENT_NAME, Entrez.email, bool(getattr(Entrez, "api_key", None)))


async def search_pubmed(plan: dict, session_id: str, queue) -> dict:
    _ensure_email()
    logger.info("[%s] search_pubmed called | session_id=%s | search_terms=%s",
                AGENT_NAME, session_id, plan.get("search_terms"))

    await emit(queue, "agent_start", AGENT_NAME, "Connecting to PubMed...")

    # Strip boolean syntax (parentheses, OR, quotes) — NCBI returns 400 for complex chains
    raw_term = plan["search_terms"][0]
    import re
    primary_term = re.sub(r'[()"]', '', raw_term).split(" OR ")[0].strip()
    search_query = primary_term + " AND diabetes AND readmission"
    logger.info("[%s] Constructed query: %r (raw term was %r)", AGENT_NAME, search_query, raw_term)

    await emit(queue, "agent_thinking", AGENT_NAME, f"Querying PubMed: {search_query}")

    loop = asyncio.get_event_loop()

    def _search():
        logger.debug("[%s] Entrez.esearch | db=pubmed | term=%r | retmax=10", AGENT_NAME, search_query)
        try:
            handle = Entrez.esearch(
                db="pubmed",
                term=search_query,
                retmax=10,
                usehistory="y",
                sort="relevance",
            )
            result = Entrez.read(handle)
            handle.close()
            logger.debug("[%s] esearch raw result | Count=%s | IdList=%s",
                         AGENT_NAME, result.get("Count"), result.get("IdList"))
            return result
        except Exception as e:
            logger.error("[%s] Entrez.esearch failed | query=%r | error=%s",
                         AGENT_NAME, search_query, e, exc_info=True)
            raise

    try:
        search_results = await loop.run_in_executor(None, _search)
    except Exception as e:
        logger.warning("[%s] Primary query failed (%s) — falling back to 'diabetes readmission'",
                       AGENT_NAME, e)
        await emit(queue, "agent_thinking", AGENT_NAME,
                   f"Primary query failed ({e}), retrying with minimal query...")

        def _fallback_search():
            fallback_term = "diabetes readmission"
            logger.debug("[%s] Fallback esearch | term=%r", AGENT_NAME, fallback_term)
            try:
                handle = Entrez.esearch(db="pubmed", term=fallback_term, retmax=5)
                result = Entrez.read(handle)
                handle.close()
                logger.debug("[%s] Fallback result | Count=%s | IdList=%s",
                             AGENT_NAME, result.get("Count"), result.get("IdList"))
                return result
            except Exception as fe:
                logger.error("[%s] Fallback search also failed | error=%s", AGENT_NAME, fe, exc_info=True)
                raise

        try:
            search_results = await loop.run_in_executor(None, _fallback_search)
        except Exception as fe2:
            logger.warning("[%s] Fallback also failed (%s) — retrying without API key", AGENT_NAME, fe2)
            await emit(queue, "agent_thinking", AGENT_NAME,
                       f"Retrying without API key...")
            saved_key = getattr(Entrez, "api_key", None)
            Entrez.api_key = None
            try:
                search_results = await loop.run_in_executor(None, _fallback_search)
            finally:
                Entrez.api_key = saved_key

    ids = search_results.get("IdList", [])
    logger.info("[%s] PubMed returned %d IDs: %s", AGENT_NAME, len(ids), ids)

    if not ids:
        logger.error("[%s] Zero results for query=%r", AGENT_NAME, search_query)
        raise Exception(f"No PubMed results found for query: {search_query!r}")

    await emit(queue, "agent_thinking", AGENT_NAME,
               f"Found {len(ids)} papers. Fetching abstracts...")

    def _fetch():
        fetch_ids = ids[:10]
        logger.debug("[%s] Entrez.efetch | ids=%s", AGENT_NAME, fetch_ids)
        try:
            handle = Entrez.efetch(
                db="pubmed",
                id=fetch_ids,
                rettype="abstract",
                retmode="xml",
            )
            result = Entrez.read(handle)
            handle.close()
            logger.debug("[%s] efetch returned %d PubmedArticle records",
                         AGENT_NAME, len(result.get("PubmedArticle", [])))
            return result
        except Exception as e:
            logger.error("[%s] Entrez.efetch failed | ids=%s | error=%s",
                         AGENT_NAME, fetch_ids, e, exc_info=True)
            raise

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
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            })
            logger.debug("[%s] Parsed paper | pmid=%s | year=%s | title=%r",
                         AGENT_NAME, pmid, year, title[:60])
        except Exception as e:
            logger.warning("[%s] Failed to parse a PubmedArticle record: %s", AGENT_NAME, e)
            continue

    logger.info("[%s] Done | parsed %d/%d papers | query=%r",
                AGENT_NAME, len(papers), len(ids), search_query)
    await emit(queue, "agent_done", AGENT_NAME,
               f"Retrieved {len(papers)} papers with abstracts",
               {"paper_count": len(papers), "papers": [p["title"] for p in papers[:5]]})

    return {"papers": papers, "search_query": search_query, "total_found": len(ids)}
