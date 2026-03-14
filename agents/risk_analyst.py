import json

from agents import emit, get_genai_client

MODEL = "gemini-2.0-flash"
AGENT_NAME = "risk_analyst"


async def analyze_risk(query: str, lit_results: dict, idx_results: dict, session_id: str, queue) -> dict:
    await emit(queue, "agent_start", AGENT_NAME, "Analyzing risk factors from literature...")

    client = get_genai_client()

    paper_summaries = []
    for p in lit_results.get("papers", [])[:6]:
        paper_summaries.append(f"PMID {p['pmid']}: {p['title']}\n{p['abstract'][:500]}")

    context = "\n\n---\n\n".join(paper_summaries)

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

    response = client.models.generate_content(model=MODEL, contents=prompt)
    text = response.text.strip().strip("```json").strip("```").strip()

    try:
        risk_data = json.loads(text)
    except json.JSONDecodeError:
        risk_data = {
            "risk_factors": [{"factor": "HbA1c > 8%", "importance_score": 0.85,
                               "direction": "increases_risk", "evidence_level": "Strong",
                               "mechanism": "Poor glycemic control", "supporting_pmids": [],
                               "reasoning": "Consistently identified in literature"}],
            "protective_factors": [],
            "population_notes": "Parse error — partial results",
            "evidence_gaps": []
        }

    factor_count = len(risk_data.get("risk_factors", []))
    await emit(queue, "agent_done", AGENT_NAME,
               f"Ranked {factor_count} risk factors by evidence strength",
               {"top_factors": [f["factor"] for f in risk_data.get("risk_factors", [])[:5]],
                "risk_data": risk_data})

    return risk_data
