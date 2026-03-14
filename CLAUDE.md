# MediSwarm — Claude Code Build Spec
## Gemini Nexus Hackathon | Track A: Intelligence Bureau | 24hr Sprint

---

## WHAT YOU ARE BUILDING

**MediSwarm** is a multi-agent AI system that answers clinical research questions about diabetic readmission risk. A user types a question like *"What reduces 30-day diabetic readmission in elderly patients?"* and a swarm of Google ADK agents autonomously searches PubMed, indexes PDFs, extracts risk factors, and produces a structured clinical brief — with all agent reasoning visible in real-time.

**Judging criteria weights (build to these):**
- 40% — Agentic agency & recovery (failure handling, reasoning traces)
- 30% — Technical depth (ADK + MCP proper implementation)
- 20% — System robustness (safety guardrails, ADK safety features)
- 10% — Docs & demo (README clarity, 150-second demo video)

---

## REPO STRUCTURE

Build exactly this structure (required by hackathon submission):

```
mediswarm/
├── agents/                  # All ADK agent logic
│   ├── __init__.py
│   ├── orchestrator.py      # Root orchestrator agent
│   ├── literature_scout.py  # PubMed search agent
│   ├── pdf_indexer.py       # PDF chunking + embedding agent
│   ├── risk_analyst.py      # Risk factor extraction agent
│   ├── synthesizer.py       # Evidence synthesis agent
│   ├── report_builder.py    # Final clinical brief agent
│   └── safety_guard.py      # LLM-as-a-Judge guardrail agent
├── tools/                   # MCP tool servers
│   ├── __init__.py
│   ├── pubmed_mcp.py        # NCBI Entrez API wrapper MCP server
│   ├── storage_mcp.py       # GCS PDF cache MCP server
│   └── vertex_mcp.py        # Vertex AI embeddings MCP server
├── app/                     # React frontend
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       ├── components/
│       │   ├── QueryInput.jsx
│       │   ├── AgentLogStream.jsx
│       │   ├── AgentCard.jsx
│       │   ├── ClinicalBrief.jsx
│       │   └── StatusBadge.jsx
│       └── index.css
├── main.py                  # FastAPI backend entry point
├── requirements.txt
├── Dockerfile               # For Cloud Run deployment
├── cloudbuild.yaml          # GCP Cloud Build config
├── .env.example             # Environment variable template
└── README.md                # Hackathon submission README
```

---

## TECH STACK

| Layer | Technology |
|-------|-----------|
| Agent framework | `google-adk` (Google Agent Development Kit) |
| LLM | Gemini 2.0 Flash (`gemini-2.0-flash`) |
| MCP protocol | Custom FastAPI MCP servers |
| Backend API | FastAPI + Server-Sent Events (SSE) for log streaming |
| Frontend | React 18 + Vite + Tailwind CSS |
| Deployment | Google Cloud Run |
| PubMed access | NCBI Entrez API (Biopython `Entrez`) |
| PDF processing | `pypdf` + `sentence-transformers` |
| Environment | Python 3.11 |

---

## AGENT ARCHITECTURE (A2A FLOW)

```
User Query
    │
    ▼
[Orchestrator Agent]  ← plans, delegates, handles failures
    │
    ├──► [Literature Scout]  → PubMed MCP → returns paper metadata list
    ├──► [PDF Indexer]       → Storage MCP + Vertex MCP → returns chunks
    ├──► [Risk Analyst]      → analyzes risk factors, SHAP-style ranking
    └──► [Synthesizer]       → merges all findings into evidence summary
                                        │
                                        ▼
                            [Safety Guard Agent]  ← LLM-as-a-Judge
                                        │
                                        ▼
                            [Report Builder Agent]
                                        │
                                        ▼
                            Structured Clinical Brief (JSON + Markdown)
```

**Critical: Every agent must emit reasoning trace events.** The frontend streams these live.

---

## SPEC FILE INDEX

Read and implement these spec files in order:

1. `SPEC_backend.md`    — FastAPI backend, SSE streaming, agent runner
2. `SPEC_agents.md`     — All 7 ADK agents with full prompts and recovery logic
3. `SPEC_tools.md`      — 3 MCP tool servers (PubMed, Storage, Vertex)
4. `SPEC_frontend.md`   — React UI with live log streaming
5. `SPEC_deploy.md`     — Dockerfile, Cloud Run, environment setup
6. `SPEC_readme.md`     — Hackathon README with A2A diagram

---

## ENVIRONMENT VARIABLES

```env
GOOGLE_API_KEY=your_gemini_api_key
GOOGLE_CLOUD_PROJECT=your_gcp_project_id
GOOGLE_CLOUD_REGION=asia-southeast1
GCS_BUCKET_NAME=mediswarm-pdf-cache
NCBI_EMAIL=your_email@example.com
NCBI_API_KEY=your_ncbi_api_key_optional
```

---

## KEY CONSTRAINTS

- **NEVER hardcode API keys** — always use `os.environ.get()`
- Use `gemini-2.0-flash` not `gemini-1.5-pro` (cost/speed for hackathon)
- Every agent response must include a `reasoning_trace` field
- The orchestrator must implement retry logic (max 2 retries per agent)
- Safety guard must block responses containing hallucinated DOIs
- Frontend must show per-agent status: `idle → thinking → done → failed`
- SSE stream must emit events for every agent state change
