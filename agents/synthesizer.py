import json

from agents import emit, get_genai_client

MODEL = "gemini-2.0-flash"
AGENT_NAME = "synthesizer"


async def synthesize_evidence(query: str, lit_results: dict, risk_results: dict, session_id: str, queue) -> dict:
    await emit(queue, "agent_start", AGENT_NAME, "Synthesizing evidence across sources...")

    client = get_genai_client()

    papers = lit_results.get("papers", [])
    top_risks = risk_results.get("risk_factors", [])[:5]
    protective = risk_results.get("protective_factors", [])[:3]

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

    response = client.models.generate_content(model=MODEL, contents=prompt)
    text = response.text.strip().strip("```json").strip("```").strip()

    try:
        synthesis = json.loads(text)
    except Exception:
        synthesis = {"executive_summary": response.text[:500],
                     "key_findings": [], "recommendations": [], "limitations": [],
                     "evidence_quality": "Low"}

    await emit(queue, "agent_done", AGENT_NAME,
               f"Synthesis complete. Evidence quality: {synthesis.get('evidence_quality', 'N/A')}",
               {"synthesis": synthesis})

    return synthesis
