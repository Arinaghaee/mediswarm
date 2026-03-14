import asyncio
import json

from agents import emit, get_genai_client

MODEL = "gemini-2.0-flash"


async def run_swarm(query: str, session_id: str, queue: asyncio.Queue):
    """
    Main orchestrator. Plans the research, delegates to sub-agents,
    handles failures with retry, and coordinates the final report.
    """
    AGENT_NAME = "orchestrator"

    try:
        await emit(queue, "agent_start", AGENT_NAME, "Planning research strategy...")

        client = get_genai_client()
        plan_prompt = f"""
        You are a medical research orchestrator. A clinician asked:
        "{query}"

        Decompose this into a structured research plan with:
        1. Key search terms for PubMed (list of 3-5 terms)
        2. Specific risk factors to look for
        3. Patient population focus
        4. Evidence type priority (RCT, meta-analysis, cohort, etc.)

        Respond in JSON only:
        {{
          "search_terms": [...],
          "risk_factors_to_find": [...],
          "population": "...",
          "evidence_priority": [...],
          "reasoning": "..."
        }}
        """

        plan_response = client.models.generate_content(model=MODEL, contents=plan_prompt)
        plan_text = plan_response.text.strip().strip("```json").strip("```").strip()
        plan = json.loads(plan_text)

        await emit(queue, "agent_thinking", AGENT_NAME,
                   f"Research plan ready. Searching for: {', '.join(plan['search_terms'][:3])}...",
                   {"plan": plan})

        from agents.literature_scout import search_pubmed
        from agents.pdf_indexer import index_pdfs
        from agents.risk_analyst import analyze_risk
        from agents.synthesizer import synthesize_evidence

        # Phase 1: Parallel data gathering
        lit_task = asyncio.create_task(search_pubmed(plan, session_id, queue))
        idx_task = asyncio.create_task(index_pdfs(plan, session_id, queue))

        lit_results, idx_results = await asyncio.gather(
            lit_task, idx_task, return_exceptions=True
        )

        # Recovery: if literature scout failed, retry once with broader terms
        if isinstance(lit_results, Exception):
            await emit(queue, "agent_thinking", AGENT_NAME,
                       f"Literature scout failed ({str(lit_results)}), retrying with broader terms...")
            plan["search_terms"] = plan["search_terms"][:2] + ["diabetes readmission", "diabetic hospital"]
            try:
                lit_results = await search_pubmed(plan, session_id, queue)
            except Exception as e:
                lit_results = {"papers": [], "error": str(e), "recovered": False}
                await emit(queue, "agent_thinking", AGENT_NAME,
                           "Literature scout failed after retry. Continuing with available data.")

        # Recovery: if pdf indexer failed, continue without it
        if isinstance(idx_results, Exception):
            await emit(queue, "agent_thinking", AGENT_NAME,
                       "PDF indexer unavailable. Proceeding with abstract-only analysis.")
            idx_results = {"chunks": [], "error": str(idx_results)}

        # Phase 2: Risk analysis
        risk_results = await analyze_risk(query, lit_results, idx_results, session_id, queue)

        # Phase 3: Synthesize
        synthesis = await synthesize_evidence(query, lit_results, risk_results, session_id, queue)

        # Phase 4: Safety check + report
        from agents.safety_guard import validate_output
        from agents.report_builder import build_report

        validated = await validate_output(synthesis, lit_results, session_id, queue)
        report = await build_report(query, validated, plan, session_id, queue)

        # Store result
        from main import sessions
        sessions[session_id]["status"] = "complete"
        sessions[session_id]["result"] = report

        await emit(queue, "swarm_complete", AGENT_NAME, "Research complete", {"report": report})

    except Exception as e:
        await emit(queue, "error", AGENT_NAME, f"Swarm failed: {str(e)}", {"error": str(e)})
