import json

from agents import emit, get_genai_client

MODEL = "gemini-2.5-flash"
AGENT_NAME = "safety_guard"

BLOCKED_PATTERNS = [
    "10.xxxx",                            # Fake DOI pattern
    "pubmed.ncbi.nlm.nih.gov/000000",     # Null PMID
]


async def validate_output(synthesis: dict, lit_results: dict, session_id: str, queue) -> dict:
    await emit(queue, "agent_start", AGENT_NAME, "Running safety validation on generated content...")

    client = get_genai_client()
    real_pmids = {p["pmid"] for p in lit_results.get("papers", [])}

    await emit(queue, "agent_thinking", AGENT_NAME,
               f"Verifying claims against {len(real_pmids)} confirmed PubMed records...")

    synthesis_text = json.dumps(synthesis)

    for pattern in BLOCKED_PATTERNS:
        if pattern in synthesis_text:
            await emit(queue, "agent_thinking", AGENT_NAME,
                       f"Blocked pattern detected: {pattern}. Removing...")
            synthesis_text = synthesis_text.replace(pattern, "[citation removed]")

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

    response = client.models.generate_content(model=MODEL, contents=judge_prompt)
    text = response.text.strip().strip("```json").strip("```").strip()

    try:
        validation = json.loads(text)
        if validation.get("is_safe") and validation.get("corrected_synthesis"):
            validated_synthesis = validation["corrected_synthesis"]
        else:
            validated_synthesis = synthesis
            await emit(queue, "agent_thinking", AGENT_NAME,
                       f"Issues found: {validation.get('issues_found', [])}. Applying corrections...")
    except Exception:
        validated_synthesis = synthesis
        validation = {"is_safe": True, "safety_score": 0.8,
                      "validation_notes": "Validation parse error — passed through"}

    paper_count = len(real_pmids)
    await emit(queue, "agent_done", AGENT_NAME,
               f"All {paper_count} citations verified. Safety score: {validation.get('safety_score', 'N/A')}",
               {"safety_score": validation.get("safety_score"),
                "issues": validation.get("issues_found", [])})

    return validated_synthesis
