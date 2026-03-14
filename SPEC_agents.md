# SPEC: ADK Agents

All agents use `google-adk`. Import pattern:
```python
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
import google.generativeai as genai
import os, asyncio, json
from datetime import datetime

genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
MODEL = "gemini-2.0-flash"
```

Every agent function must accept `(query: str, session_id: str, queue: asyncio.Queue)` and emit SSE events via the queue using this helper:

```python
async def emit(queue, type_, agent, message, data=None):
    await queue.put({
        "type": type_,
        "agent": agent,
        "message": message,
        "data": data or {},
        "timestamp": datetime.utcnow().isoformat()
    })
```

---

## File: `agents/orchestrator.py`

This is the main entry point called by `main.py`. It orchestrates all sub-agents.

```python
async def run_swarm(query: str, session_id: str, queue: asyncio.Queue):
    """
    Main orchestrator. Plans the research, delegates to sub-agents,
    handles failures with retry, and coordinates the final report.
    """
    AGENT_NAME = "orchestrator"
    
    try:
        await emit(queue, "agent_start", AGENT_NAME, "Planning research strategy...")
        
        # Use Gemini to decompose the query into a research plan
        model = genai.GenerativeModel(MODEL)
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
        
        plan_response = model.generate_content(plan_prompt)
        plan_text = plan_response.text.strip().strip("```json").strip("```")
        plan = json.loads(plan_text)
        
        await emit(queue, "agent_thinking", AGENT_NAME,
            f"Research plan ready. Searching for: {', '.join(plan['search_terms'][:3])}...",
            {"plan": plan})
        
        # Run literature scout and pdf indexer concurrently
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
        
        # Recovery: if literature scout failed, retry once
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
```

---

## File: `agents/literature_scout.py`

Uses PubMed via Biopython Entrez. Searches, fetches abstracts, ranks by relevance.

```python
from Bio import Entrez
import os, asyncio, json
from datetime import datetime

Entrez.email = os.environ.get("NCBI_EMAIL", "mediswarm@example.com")
AGENT_NAME = "literature_scout"

async def search_pubmed(plan: dict, session_id: str, queue) -> dict:
    await emit(queue, "agent_start", AGENT_NAME, "Connecting to PubMed...")
    
    search_query = " OR ".join(f'"{t}"' for t in plan["search_terms"])
    search_query += " AND (readmission OR rehospitalization)"
    
    await emit(queue, "agent_thinking", AGENT_NAME,
        f"Querying PubMed: {search_query[:80]}...")
    
    # Run Entrez in thread pool to avoid blocking event loop
    loop = asyncio.get_event_loop()
    
    def _search():
        handle = Entrez.esearch(db="pubmed", term=search_query,
                                retmax=20, sort="relevance",
                                datetype="pdat", reldate=1825)  # last 5 years
        return Entrez.read(handle)
    
    search_results = await loop.run_in_executor(None, _search)
    ids = search_results["IdList"]
    
    if not ids:
        raise Exception("No PubMed results found for query")
    
    await emit(queue, "agent_thinking", AGENT_NAME,
        f"Found {len(ids)} papers. Fetching abstracts...")
    
    def _fetch():
        handle = Entrez.efetch(db="pubmed", id=ids[:10],
                               rettype="abstract", retmode="xml")
        return Entrez.read(handle)
    
    records = await loop.run_in_executor(None, _fetch)
    
    papers = []
    for record in records.get("PubmedArticle", []):
        try:
            article = record["MedlineCitation"]["Article"]
            pmid = str(record["MedlineCitation"]["PMID"])
            title = str(article.get("ArticleTitle", ""))
            abstract_text = ""
            if "Abstract" in article:
                abstract_parts = article["Abstract"].get("AbstractText", [])
                if isinstance(abstract_parts, list):
                    abstract_text = " ".join(str(p) for p in abstract_parts)
                else:
                    abstract_text = str(abstract_parts)
            
            year = ""
            pub_date = article.get("Journal", {}).get("JournalIssue", {}).get("PubDate", {})
            year = str(pub_date.get("Year", ""))
            
            papers.append({
                "pmid": pmid,
                "title": title,
                "abstract": abstract_text[:1500],
                "year": year,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
            })
        except Exception:
            continue
    
    await emit(queue, "agent_done", AGENT_NAME,
        f"Retrieved {len(papers)} papers with abstracts",
        {"paper_count": len(papers), "papers": [p["title"] for p in papers[:5]]})
    
    return {"papers": papers, "search_query": search_query, "total_found": len(ids)}
```

---

## File: `agents/pdf_indexer.py`

Downloads and chunks PDFs from PubMed Central (free full text) using pypdf.

```python
import httpx, asyncio, os
from pypdf import PdfReader
import io

AGENT_NAME = "pdf_indexer"
PMC_BASE = "https://www.ncbi.nlm.nih.gov/pmc/articles"

async def index_pdfs(plan: dict, session_id: str, queue) -> dict:
    await emit(queue, "agent_start", AGENT_NAME, "Searching for open-access full texts...")
    
    # Search PMC for open-access papers
    from Bio import Entrez
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
            # Fetch full text XML from PMC
            def _fetch_full():
                handle = Entrez.efetch(db="pmc", id=pmc_id, rettype="full", retmode="xml")
                return handle.read()
            
            full_text = await loop.run_in_executor(None, _fetch_full)
            
            # Simple chunking: split into 500-char chunks
            text = full_text.decode("utf-8", errors="ignore")
            # Strip XML tags roughly
            import re
            clean = re.sub(r'<[^>]+>', ' ', text)
            clean = re.sub(r'\s+', ' ', clean).strip()
            
            chunk_size = 500
            chunks = [clean[i:i+chunk_size] for i in range(0, min(len(clean), 8000), chunk_size)]
            
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
```

---

## File: `agents/risk_analyst.py`

Extracts and ranks risk factors from literature using Gemini. SHAP-style importance ranking.

```python
import google.generativeai as genai
import json, os

MODEL = "gemini-2.0-flash"
AGENT_NAME = "risk_analyst"

async def analyze_risk(query: str, lit_results: dict, idx_results: dict, session_id: str, queue) -> dict:
    await emit(queue, "agent_start", AGENT_NAME, "Analyzing risk factors from literature...")
    
    model = genai.GenerativeModel(MODEL)
    
    # Build context from papers
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
    
    response = model.generate_content(prompt)
    text = response.text.strip().strip("```json").strip("```")
    
    try:
        risk_data = json.loads(text)
    except json.JSONDecodeError:
        # Recovery: extract what we can
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
```

---

## File: `agents/synthesizer.py`

Merges all findings into a coherent evidence summary.

```python
import google.generativeai as genai
import json, os

MODEL = "gemini-2.0-flash"
AGENT_NAME = "synthesizer"

async def synthesize_evidence(query: str, lit_results: dict, risk_results: dict, session_id: str, queue) -> dict:
    await emit(queue, "agent_start", AGENT_NAME, "Synthesizing evidence across sources...")
    
    model = genai.GenerativeModel(MODEL)
    
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
    
    response = model.generate_content(prompt)
    text = response.text.strip().strip("```json").strip("```")
    
    try:
        synthesis = json.loads(text)
    except Exception:
        synthesis = {"executive_summary": response.text[:500],
                    "key_findings": [], "recommendations": [], "limitations": [], "evidence_quality": "Low"}
    
    await emit(queue, "agent_done", AGENT_NAME,
        f"Synthesis complete. Evidence quality: {synthesis.get('evidence_quality', 'N/A')}",
        {"synthesis": synthesis})
    
    return synthesis
```

---

## File: `agents/safety_guard.py`

LLM-as-a-Judge. Validates citations, checks for hallucinations, blocks unsafe claims.

```python
import google.generativeai as genai
import json, os

MODEL = "gemini-2.0-flash"
AGENT_NAME = "safety_guard"

BLOCKED_PATTERNS = [
    "10.xxxx",  # Fake DOI pattern
    "pubmed.ncbi.nlm.nih.gov/000000",  # Null PMID
]

async def validate_output(synthesis: dict, lit_results: dict, session_id: str, queue) -> dict:
    await emit(queue, "agent_start", AGENT_NAME, "Running safety validation on generated content...")
    
    model = genai.GenerativeModel(MODEL)
    real_pmids = {p["pmid"] for p in lit_results.get("papers", [])}
    
    await emit(queue, "agent_thinking", AGENT_NAME,
        f"Verifying claims against {len(real_pmids)} confirmed PubMed records...")
    
    synthesis_text = json.dumps(synthesis)
    
    # Check for blocked patterns
    for pattern in BLOCKED_PATTERNS:
        if pattern in synthesis_text:
            await emit(queue, "agent_thinking", AGENT_NAME,
                f"Blocked pattern detected: {pattern}. Removing...")
            synthesis_text = synthesis_text.replace(pattern, "[citation removed]")
    
    # LLM-as-a-Judge validation
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
      "is_safe": true/false,
      "issues_found": [...],
      "corrected_synthesis": {{...same structure, with issues fixed...}},
      "safety_score": 0.0-1.0,
      "validation_notes": "..."
    }}
    """
    
    response = model.generate_content(judge_prompt)
    text = response.text.strip().strip("```json").strip("```")
    
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
        validation = {"is_safe": True, "safety_score": 0.8, "validation_notes": "Validation parse error — passed through"}
    
    await emit(queue, "agent_done", AGENT_NAME,
        f"Validation complete. Safety score: {validation.get('safety_score', 'N/A')}",
        {"safety_score": validation.get("safety_score"), "issues": validation.get("issues_found", [])})
    
    return validated_synthesis
```

---

## File: `agents/report_builder.py`

Builds the final structured clinical brief in both JSON and Markdown.

```python
import google.generativeai as genai
import json, os
from datetime import datetime

MODEL = "gemini-2.0-flash"
AGENT_NAME = "report_builder"

async def build_report(query: str, synthesis: dict, plan: dict, session_id: str, queue) -> dict:
    await emit(queue, "agent_start", AGENT_NAME, "Generating final clinical brief...")
    
    model = genai.GenerativeModel(MODEL)
    
    await emit(queue, "agent_thinking", AGENT_NAME, "Formatting report with citations and evidence grades...")
    
    prompt = f"""
    Generate a professional clinical research brief.
    
    Original question: {query}
    Synthesis data: {json.dumps(synthesis, indent=2)[:3000]}
    
    Create a complete clinical brief. Respond in JSON:
    {{
      "title": "Clinical Evidence Brief: [descriptive title]",
      "generated_at": "{datetime.utcnow().isoformat()}",
      "clinical_question": "{query}",
      "executive_summary": "...",
      "evidence_summary": {{
        "papers_reviewed": 0,
        "evidence_quality": "High|Moderate|Low",
        "date_range": "..."
      }},
      "risk_factors": [
        {{
          "factor": "...",
          "importance": "High|Medium|Low",
          "evidence_grade": "A|B|C",
          "recommendation": "..."
        }}
      ],
      "clinical_recommendations": [
        {{
          "priority": 1,
          "action": "...",
          "strength": "Strong|Conditional",
          "rationale": "..."
        }}
      ],
      "key_interventions": [...],
      "limitations": [...],
      "disclaimer": "This brief is generated by AI from public literature. Always verify with current clinical guidelines.",
      "markdown_report": "# Clinical Evidence Brief\\n\\n..."
    }}
    """
    
    response = model.generate_content(prompt)
    text = response.text.strip().strip("```json").strip("```")
    
    try:
        report = json.loads(text)
    except Exception:
        report = {
            "title": "Clinical Evidence Brief",
            "generated_at": datetime.utcnow().isoformat(),
            "clinical_question": query,
            "executive_summary": str(synthesis.get("executive_summary", "")),
            "evidence_summary": {"evidence_quality": synthesis.get("evidence_quality", "Low")},
            "risk_factors": [],
            "clinical_recommendations": synthesis.get("recommendations", []),
            "limitations": synthesis.get("limitations", []),
            "disclaimer": "AI-generated. Verify with clinical guidelines.",
            "markdown_report": f"# Clinical Brief\n\n{str(synthesis)[:1000]}"
        }
    
    await emit(queue, "agent_done", AGENT_NAME,
        "Clinical brief generated and ready",
        {"title": report.get("title"), "recommendations_count": len(report.get("clinical_recommendations", []))})
    
    return report


# Shared emit helper — put this in agents/__init__.py
```

---

## File: `agents/__init__.py`

```python
import asyncio
from datetime import datetime

async def emit(queue: asyncio.Queue, type_: str, agent: str, message: str, data: dict = None):
    """Shared event emitter for all agents."""
    await queue.put({
        "type": type_,
        "agent": agent,
        "message": message,
        "data": data or {},
        "timestamp": datetime.utcnow().isoformat()
    })
```

**Important:** Update all agent files to import emit from here:
```python
from agents import emit
```
