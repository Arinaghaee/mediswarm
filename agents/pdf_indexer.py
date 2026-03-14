import asyncio
import re

from Bio import Entrez

from agents import emit

AGENT_NAME = "pdf_indexer"


async def index_pdfs(plan: dict, session_id: str, queue) -> dict:
    await emit(queue, "agent_start", AGENT_NAME, "Searching for open-access full texts...")

    loop = asyncio.get_event_loop()

    search_q = " ".join(plan["search_terms"][:3]) + " diabetes readmission"

    def _pmc_search():
        handle = Entrez.esearch(db="pmc", term=search_q + " AND open access[filter]",
                                retmax=5, sort="relevance")
        return Entrez.read(handle)

    await emit(queue, "agent_thinking", AGENT_NAME, "Querying PubMed Central for open-access PDFs...")

    try:
        pmc_results = await loop.run_in_executor(None, _pmc_search)
        pmc_ids = pmc_results.get("IdList", [])
    except Exception:
        pmc_ids = []

    if not pmc_ids:
        await emit(queue, "agent_done", AGENT_NAME,
                   "No open-access PDFs found. Using abstract-only mode.", {"chunks": []})
        return {"chunks": [], "mode": "abstract_only"}

    await emit(queue, "agent_thinking", AGENT_NAME,
               f"Found {len(pmc_ids)} open-access papers. Chunking text...")

    all_chunks = []
    for pmc_id in pmc_ids[:3]:
        try:
            def _fetch_full(pid=pmc_id):
                handle = Entrez.efetch(db="pmc", id=pid, rettype="full", retmode="xml")
                return handle.read()

            full_text = await loop.run_in_executor(None, _fetch_full)

            # Simple chunking: split into 500-char chunks
            text = full_text.decode("utf-8", errors="ignore")
            # Strip XML tags roughly
            clean = re.sub(r'<[^>]+>', ' ', text)
            clean = re.sub(r'\s+', ' ', clean).strip()

            chunk_size = 500
            chunks = [clean[i:i + chunk_size] for i in range(0, min(len(clean), 8000), chunk_size)]

            for i, chunk in enumerate(chunks):
                all_chunks.append({
                    "pmc_id": pmc_id,
                    "chunk_index": i,
                    "text": chunk
                })
        except Exception:
            continue

    await emit(queue, "agent_done", AGENT_NAME,
               f"Indexed {len(all_chunks)} text chunks from {len(pmc_ids)} papers",
               {"chunk_count": len(all_chunks), "paper_count": len(pmc_ids)})

    return {"chunks": all_chunks, "paper_count": len(pmc_ids), "mode": "full_text"}
