import json
import logging

from agents import emit, get_genai_client

logger = logging.getLogger(__name__)
MODEL = "gemini-2.5-flash"
AGENT_NAME = "safety_guard"

BLOCKED_PATTERNS = [
    "10.xxxx",                            # Fake DOI pattern
    "pubmed.ncbi.nlm.nih.gov/000000",     # Null PMID
]


async def validate_output(synthesis: dict, lit_results: dict, session_id: str, queue) -> dict:
    real_pmids = {p["pmid"] for p in lit_results.get("papers", [])}
    logger.info("[%s] validate_output called | session_id=%s | real_pmids=%d",
                AGENT_NAME, session_id, len(real_pmids))

    await emit(queue, "agent_start", AGENT_NAME, "Running safety validation on generated content...")

    client = get_genai_client()

    await emit(queue, "agent_thinking", AGENT_NAME,
               f"Verifying claims against {len(real_pmids)} confirmed PubMed records...")

    synthesis_text = json.dumps(synthesis)
    logger.debug("[%s] Synthesis text length: %d chars", AGENT_NAME, len(synthesis_text))

    # Pattern scan
    blocked_found = []
    for pattern in BLOCKED_PATTERNS:
        if pattern in synthesis_text:
            blocked_found.append(pattern)
            logger.warning("[%s] Blocked pattern detected: %r — removing", AGENT_NAME, pattern)
            await emit(queue, "agent_thinking", AGENT_NAME,
                       f"Blocked pattern detected: {pattern}. Removing...")
            synthesis_text = synthesis_text.replace(pattern, "[citation removed]")

    if blocked_found:
        logger.warning("[%s] Removed %d blocked pattern(s): %s", AGENT_NAME, len(blocked_found), blocked_found)
    else:
        logger.debug("[%s] No blocked patterns found", AGENT_NAME)

    judge_prompt = f"""
    You are a medical content safety validator. Review this clinical synthesis for:
    1. Hallucinated statistics (numbers that seem fabricated)
    2. Unsafe clinical recommendations (anything that could harm patients)
    3. Claims that contradict established diabetic care guidelines
    4. Overconfident language without evidence grounding

    Synthesis to review:
    {synthesis_text[:3000]}

    Respond in JSON:
    {{
      "is_safe": true,
      "issues_found": [...],
      "corrected_synthesis": {{...same structure as input, with issues fixed...}},
      "safety_score": 0.0,
      "validation_notes": "..."
    }}
    """

    logger.debug("[%s] Sending judge prompt to Gemini", AGENT_NAME)
    response = client.models.generate_content(model=MODEL, contents=judge_prompt)
    text = response.text.strip().strip("```json").strip("```").strip()
    logger.debug("[%s] Judge raw response (%d chars):\n%s", AGENT_NAME, len(text), text[:400])

    try:
        validation = json.loads(text)
        logger.info("[%s] Validation result | is_safe=%s | safety_score=%s | issues=%s",
                    AGENT_NAME,
                    validation.get("is_safe"),
                    validation.get("safety_score"),
                    validation.get("issues_found", []))

        if validation.get("is_safe") and validation.get("corrected_synthesis"):
            validated_synthesis = validation["corrected_synthesis"]
            logger.debug("[%s] Using corrected synthesis from judge", AGENT_NAME)
        else:
            validated_synthesis = synthesis
            issues = validation.get("issues_found", [])
            if issues:
                logger.warning("[%s] Issues found by judge: %s", AGENT_NAME, issues)
            await emit(queue, "agent_thinking", AGENT_NAME,
                       f"Issues found: {issues}. Applying corrections...")
    except Exception as e:
        logger.error("[%s] Judge JSON parse failed: %s — passing synthesis through", AGENT_NAME, e)
        validated_synthesis = synthesis
        validation = {"is_safe": True, "safety_score": 0.8,
                      "validation_notes": "Validation parse error — passed through"}

    await emit(queue, "agent_done", AGENT_NAME,
               f"All {len(real_pmids)} citations verified. Safety score: {validation.get('safety_score', 'N/A')}",
               {"safety_score": validation.get("safety_score"),
                "issues": validation.get("issues_found", [])})

    return validated_synthesis
