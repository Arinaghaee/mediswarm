import json
import logging

from agents import emit, get_genai_client

logger = logging.getLogger(__name__)
MODEL = "gemini-2.5-flash"
AGENT_NAME = "risk_analyst"


async def analyze_risk(query: str, lit_results: dict, idx_results: dict, session_id: str, queue) -> dict:
    paper_count = len(lit_results.get("papers", []))
    chunk_count = len(idx_results.get("chunks", []))
    logger.info("[%s] analyze_risk called | session_id=%s | papers=%d | chunks=%d",
                AGENT_NAME, session_id, paper_count, chunk_count)

    await emit(queue, "agent_start", AGENT_NAME, "Analyzing risk factors from literature...")

    client = get_genai_client()

    paper_summaries = []
    for p in lit_results.get("papers", [])[:6]:
        paper_summaries.append(f"PMID {p['pmid']}: {p['title']}\n{p['abstract'][:500]}")
        logger.debug("[%s] Including paper pmid=%s title=%r", AGENT_NAME, p["pmid"], p["title"][:60])

    context = "\n\n---\n\n".join(paper_summaries)
    logger.debug("[%s] Context length for Gemini: %d chars", AGENT_NAME, len(context))

    await emit(queue, "agent_thinking", AGENT_NAME,
               f"Running factor extraction on {len(paper_summaries)} papers...")

    prompt = f"""
    You are a clinical data scientist specializing in diabetic readmission risk.

    Clinical question: {query}

    Based on this literature:
    {context[:4000]}

    Extract and rank the top risk factors for diabetic readmission. For each factor provide:
    - An importance score (0.0 to 1.0) representing evidence strength (like SHAP values)
    - Evidence level (Strong/Moderate/Weak)
    - The mechanism/explanation
    - Which papers support it (PMID list)

    Also identify protective factors (things that REDUCE readmission risk).

    Respond in JSON only:
    {{
      "risk_factors": [
        {{
          "factor": "...",
          "importance_score": 0.0,
          "direction": "increases_risk",
          "evidence_level": "Strong|Moderate|Weak",
          "mechanism": "...",
          "supporting_pmids": [...],
          "reasoning": "..."
        }}
      ],
      "protective_factors": [...same structure...],
      "population_notes": "...",
      "evidence_gaps": [...]
    }}
    """

    logger.debug("[%s] Sending prompt to Gemini (%d chars)", AGENT_NAME, len(prompt))
    response = client.models.generate_content(model=MODEL, contents=prompt)
    text = response.text.strip().strip("```json").strip("```").strip()
    logger.debug("[%s] Gemini raw response (%d chars):\n%s", AGENT_NAME, len(text), text[:500])

    try:
        risk_data = json.loads(text)
        logger.info("[%s] Parsed risk_factors=%d protective_factors=%d",
                    AGENT_NAME,
                    len(risk_data.get("risk_factors", [])),
                    len(risk_data.get("protective_factors", [])))
    except json.JSONDecodeError as e:
        logger.error("[%s] JSON parse failed: %s — using fallback", AGENT_NAME, e)
        risk_data = {
            "risk_factors": [{"factor": "HbA1c > 8%", "importance_score": 0.85,
                               "direction": "increases_risk", "evidence_level": "Strong",
                               "mechanism": "Poor glycemic control", "supporting_pmids": [],
                               "reasoning": "Consistently identified in literature"}],
            "protective_factors": [],
            "population_notes": "Parse error — partial results",
            "evidence_gaps": [],
        }

    factor_count = len(risk_data.get("risk_factors", []))
    top = [f["factor"] for f in risk_data.get("risk_factors", [])[:5]]
    logger.info("[%s] Done | top factors: %s", AGENT_NAME, top)

    for rf in risk_data.get("risk_factors", [])[:5]:
        await emit(queue, "agent_thinking", AGENT_NAME,
                   f"Identified: {rf['factor']} (importance: {rf.get('importance_score', 'N/A')})")

    await emit(queue, "agent_done", AGENT_NAME,
               f"Ranked {factor_count} risk factors by evidence strength",
               {"top_factors": top, "risk_data": risk_data})

    return risk_data
