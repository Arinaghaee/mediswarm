import json
import logging

from agents import emit, get_genai_client

logger = logging.getLogger(__name__)
MODEL = "gemini-2.5-flash"
AGENT_NAME = "synthesizer"


async def synthesize_evidence(query: str, lit_results: dict, risk_results: dict, session_id: str, queue) -> dict:
    papers = lit_results.get("papers", [])
    top_risks = risk_results.get("risk_factors", [])[:5]
    protective = risk_results.get("protective_factors", [])[:3]

    logger.info("[%s] synthesize_evidence called | session_id=%s | papers=%d | risk_factors=%d | protective=%d",
                AGENT_NAME, session_id, len(papers), len(top_risks), len(protective))

    await emit(queue, "agent_start", AGENT_NAME, "Synthesizing evidence across sources...")

    client = get_genai_client()

    await emit(queue, "agent_thinking", AGENT_NAME,
               f"Merging findings from {len(papers)} papers and {len(top_risks)} risk factors...")

    prompt = f"""
    Synthesize clinical evidence for: {query}

    Top risk factors identified: {json.dumps(top_risks, indent=2)[:2000]}
    Protective factors: {json.dumps(protective, indent=2)[:1000]}
    Papers reviewed: {len(papers)}

    Create a structured evidence synthesis with:
    1. Executive summary (2-3 sentences)
    2. Key findings with evidence grades (A/B/C)
    3. Clinical recommendations (actionable, specific)
    4. Limitations of current evidence

    Respond in JSON:
    {{
      "executive_summary": "...",
      "key_findings": [
        {{"finding": "...", "evidence_grade": "A|B|C", "clinical_implication": "..."}}
      ],
      "recommendations": [
        {{"action": "...", "strength": "Strong|Conditional", "rationale": "..."}}
      ],
      "limitations": [...],
      "evidence_quality": "High|Moderate|Low"
    }}
    """

    logger.debug("[%s] Sending synthesis prompt to Gemini (%d chars)", AGENT_NAME, len(prompt))
    response = client.models.generate_content(model=MODEL, contents=prompt)
    text = response.text.strip().strip("```json").strip("```").strip()
    logger.debug("[%s] Gemini raw response (%d chars):\n%s", AGENT_NAME, len(text), text[:400])

    try:
        synthesis = json.loads(text)
        logger.info("[%s] Synthesis parsed | evidence_quality=%s | findings=%d | recommendations=%d",
                    AGENT_NAME,
                    synthesis.get("evidence_quality"),
                    len(synthesis.get("key_findings", [])),
                    len(synthesis.get("recommendations", [])))
    except Exception as e:
        logger.error("[%s] JSON parse failed: %s — using raw text fallback", AGENT_NAME, e)
        synthesis = {"executive_summary": response.text[:500],
                     "key_findings": [], "recommendations": [], "limitations": [],
                     "evidence_quality": "Low"}

    await emit(queue, "agent_done", AGENT_NAME,
               f"Synthesis complete. Evidence quality: {synthesis.get('evidence_quality', 'N/A')}",
               {"synthesis": synthesis})

    return synthesis
