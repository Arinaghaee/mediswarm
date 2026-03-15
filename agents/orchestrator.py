import asyncio
import json
import logging

from agents import emit, get_genai_client

logger = logging.getLogger(__name__)
MODEL = "gemini-2.5-flash"


async def run_swarm(query: str, session_id: str, queue: asyncio.Queue):
    """
    Main orchestrator. Plans the research, delegates to sub-agents,
    handles failures with retry, and coordinates the final report.
    """
    AGENT_NAME = "orchestrator"
    logger.info("[%s] run_swarm started | session_id=%s | query=%r", AGENT_NAME, session_id, query)

    try:
        await emit(queue, "agent_start", AGENT_NAME, "Planning research strategy...")

        logger.debug("[%s] Calling Gemini to build research plan...", AGENT_NAME)
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
        logger.debug("[%s] Raw plan response:\n%s", AGENT_NAME, plan_text)

        plan = json.loads(plan_text)
        logger.info("[%s] Research plan | search_terms=%s | population=%r",
                    AGENT_NAME, plan.get("search_terms"), plan.get("population"))

        await emit(queue, "agent_thinking", AGENT_NAME,
                   f"Research plan ready. Searching for: {', '.join(plan['search_terms'][:3])}...",
                   {"plan": plan})

        from agents.literature_scout import search_pubmed
        from agents.pdf_indexer import index_pdfs
        from agents.risk_analyst import analyze_risk
        from agents.synthesizer import synthesize_evidence

        # Phase 1: Parallel data gathering
        logger.info("[%s] Phase 1 — launching literature_scout + pdf_indexer in parallel", AGENT_NAME)
        await emit(queue, "agent_thinking", AGENT_NAME,
                   "Delegating to literature_scout and pdf_indexer in parallel")
        lit_task = asyncio.create_task(search_pubmed(plan, session_id, queue))
        idx_task = asyncio.create_task(index_pdfs(plan, session_id, queue))

        lit_results, idx_results = await asyncio.gather(
            lit_task, idx_task, return_exceptions=True
        )

        # Recovery: if literature scout failed, retry once with broader terms
        if isinstance(lit_results, Exception):
            logger.warning("[%s] literature_scout failed: %s — retrying with broader terms",
                           AGENT_NAME, lit_results)
            await emit(queue, "agent_thinking", AGENT_NAME,
                       f"Literature scout failed ({str(lit_results)}), retrying with broader terms...")
            plan["search_terms"] = plan["search_terms"][:2] + ["diabetes readmission", "diabetic hospital"]
            logger.debug("[%s] Retry search_terms=%s", AGENT_NAME, plan["search_terms"])
            try:
                lit_results = await search_pubmed(plan, session_id, queue)
            except Exception as e:
                logger.error("[%s] literature_scout retry also failed: %s", AGENT_NAME, e)
                lit_results = {"papers": [], "error": str(e), "recovered": False}
                await emit(queue, "agent_thinking", AGENT_NAME,
                           "Literature scout failed after retry. Continuing with available data.")
        else:
            logger.info("[%s] literature_scout succeeded | papers=%d",
                        AGENT_NAME, len(lit_results.get("papers", [])))

        # Recovery: if pdf indexer failed, continue without it
        if isinstance(idx_results, Exception):
            logger.warning("[%s] pdf_indexer failed: %s — continuing without full-text chunks",
                           AGENT_NAME, idx_results)
            await emit(queue, "agent_thinking", AGENT_NAME,
                       "PDF indexer unavailable. Proceeding with abstract-only analysis.")
            idx_results = {"chunks": [], "error": str(idx_results)}
        else:
            logger.info("[%s] pdf_indexer succeeded | chunks=%d",
                        AGENT_NAME, len(idx_results.get("chunks", [])))

        # Phase 2: Risk analysis
        logger.info("[%s] Phase 2 — risk analysis", AGENT_NAME)
        risk_results = await analyze_risk(query, lit_results, idx_results, session_id, queue)
        logger.info("[%s] risk_analyst done | risk_factors=%d | protective_factors=%d",
                    AGENT_NAME,
                    len(risk_results.get("risk_factors", [])),
                    len(risk_results.get("protective_factors", [])))

        # Phase 3: Synthesize
        logger.info("[%s] Phase 3 — evidence synthesis", AGENT_NAME)
        synthesis = await synthesize_evidence(query, lit_results, risk_results, session_id, queue)
        logger.info("[%s] synthesizer done | evidence_quality=%s",
                    AGENT_NAME, synthesis.get("evidence_quality"))

        # Phase 4: Safety check + report
        logger.info("[%s] Phase 4 — safety validation + report building", AGENT_NAME)
        from agents.safety_guard import validate_output
        from agents.report_builder import build_report

        validated = await validate_output(synthesis, lit_results, session_id, queue)
        report = await build_report(query, validated, plan, session_id, queue)
        logger.info("[%s] Report built | title=%r | recommendations=%d",
                    AGENT_NAME, report.get("title"),
                    len(report.get("clinical_recommendations", [])))

        # Store result
        from main import sessions
        sessions[session_id]["status"] = "complete"
        sessions[session_id]["result"] = report

        logger.info("[%s] Swarm complete | session_id=%s", AGENT_NAME, session_id)
        await emit(queue, "swarm_complete", AGENT_NAME, "Research complete", {"report": report})

    except Exception as e:
        logger.exception("[%s] Unhandled swarm error | session_id=%s", AGENT_NAME, session_id)
        await emit(queue, "error", AGENT_NAME, f"Swarm failed: {str(e)}", {"error": str(e)})
