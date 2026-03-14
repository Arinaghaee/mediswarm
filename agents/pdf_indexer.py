import asyncio
import logging
import re

from Bio import Entrez

from agents import emit

logger = logging.getLogger(__name__)
AGENT_NAME = "pdf_indexer"


async def index_pdfs(plan: dict, session_id: str, queue) -> dict:
    logger.info("[%s] index_pdfs called | session_id=%s", AGENT_NAME, session_id)
    await emit(queue, "agent_start", AGENT_NAME, "Searching for open-access full texts...")

    loop = asyncio.get_event_loop()
    search_q = " ".join(plan["search_terms"][:3]) + " diabetes readmission"
    pmc_query = search_q + " AND open access[filter]"
    logger.debug("[%s] PMC search query: %r", AGENT_NAME, pmc_query)

    def _pmc_search():
        try:
            logger.debug("[%s] Entrez.esearch | db=pmc | term=%r | retmax=5", AGENT_NAME, pmc_query)
            handle = Entrez.esearch(db="pmc", term=pmc_query, retmax=5, sort="relevance")
            result = Entrez.read(handle)
            handle.close()
            logger.debug("[%s] PMC esearch result | Count=%s | IdList=%s",
                         AGENT_NAME, result.get("Count"), result.get("IdList"))
            return result
        except Exception as e:
            logger.error("[%s] PMC esearch failed | error=%s", AGENT_NAME, e, exc_info=True)
            raise

    await emit(queue, "agent_thinking", AGENT_NAME, "Querying PubMed Central for open-access PDFs...")

    try:
        pmc_results = await loop.run_in_executor(None, _pmc_search)
        pmc_ids = pmc_results.get("IdList", [])
        logger.info("[%s] Found %d PMC IDs: %s", AGENT_NAME, len(pmc_ids), pmc_ids)
    except Exception as e:
        logger.warning("[%s] PMC search failed (%s) — falling back to abstract-only mode", AGENT_NAME, e)
        pmc_ids = []

    if not pmc_ids:
        logger.info("[%s] No open-access PDFs found — abstract-only mode", AGENT_NAME)
        await emit(queue, "agent_done", AGENT_NAME,
                   "No open-access PDFs found. Using abstract-only mode.", {"chunks": []})
        return {"chunks": [], "mode": "abstract_only"}

    await emit(queue, "agent_thinking", AGENT_NAME,
               f"Found {len(pmc_ids)} open-access papers. Chunking text...")

    all_chunks = []
    for pmc_id in pmc_ids[:3]:
        logger.debug("[%s] Fetching full text for PMC ID: %s", AGENT_NAME, pmc_id)
        try:
            def _fetch_full(pid=pmc_id):
                try:
                    handle = Entrez.efetch(db="pmc", id=pid, rettype="full", retmode="xml")
                    data = handle.read()
                    handle.close()
                    logger.debug("[%s] Fetched %d bytes for pmc_id=%s", AGENT_NAME, len(data), pid)
                    return data
                except Exception as e:
                    logger.error("[%s] efetch failed for pmc_id=%s | error=%s", AGENT_NAME, pid, e)
                    raise

            full_text = await loop.run_in_executor(None, _fetch_full)

            text = full_text.decode("utf-8", errors="ignore")
            clean = re.sub(r'<[^>]+>', ' ', text)
            clean = re.sub(r'\s+', ' ', clean).strip()

            chunk_size = 500
            chunks = [clean[i:i + chunk_size] for i in range(0, min(len(clean), 8000), chunk_size)]

            for i, chunk in enumerate(chunks):
                all_chunks.append({"pmc_id": pmc_id, "chunk_index": i, "text": chunk})

            logger.debug("[%s] pmc_id=%s produced %d chunks", AGENT_NAME, pmc_id, len(chunks))
        except Exception as e:
            logger.warning("[%s] Skipping pmc_id=%s due to error: %s", AGENT_NAME, pmc_id, e)
            continue

    logger.info("[%s] Done | total_chunks=%d from %d papers", AGENT_NAME, len(all_chunks), len(pmc_ids))
    await emit(queue, "agent_done", AGENT_NAME,
               f"Indexed {len(all_chunks)} text chunks from {len(pmc_ids)} papers",
               {"chunk_count": len(all_chunks), "paper_count": len(pmc_ids)})

    return {"chunks": all_chunks, "paper_count": len(pmc_ids), "mode": "full_text"}
