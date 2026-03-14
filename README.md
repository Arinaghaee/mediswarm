# MediSwarm 🧠⬡
### Diabetic Readmission Research Intelligence — Multi-Agent Swarm

> Gemini Nexus Hackathon 2026 | Track A: Intelligence Bureau | Solo Submission

**Live Demo:** https://YOUR_CLOUD_RUN_URL
**Demo Video:** https://youtube.com/watch?v=YOUR_VIDEO_ID

---

## What It Does

MediSwarm answers clinical research questions about diabetic readmission risk using a coordinated swarm of AI agents. Ask a question like *"What reduces 30-day diabetic readmission in elderly patients?"* and watch 7 specialized agents autonomously search PubMed, index full-text papers, extract evidence-graded risk factors, and produce a structured clinical brief — with all reasoning visible in real-time.

---

## System Architecture (A2A Flow)

```
User Clinical Query
        │
        ▼
┌─────────────────────────────────┐
│       Orchestrator Agent        │  Plans, delegates, recovers from failures
│     (Google ADK LlmAgent)       │  Emits reasoning traces throughout
└──────┬────────┬────────┬────────┘
       │        │        │
       ▼        ▼        ▼
 [Lit Scout] [PDF Idx] [Risk Analyst]  ← Parallel execution
  PubMed MCP  Storage   SHAP-style
              MCP       ranking
       │        │        │
       └────────┴────────┘
                │
                ▼
        [Synthesizer Agent]
         Evidence merging
                │
                ▼
        [Safety Guard Agent]   ← LLM-as-a-Judge
         Citation validation      Hallucination check
                │
                ▼
       [Report Builder Agent]
        Clinical brief (JSON + MD)
                │
                ▼
         React UI (SSE stream)
```

---

## Agent Profiles

| Agent | Role | MCP Tools Used | Recovery Behavior |
|-------|------|----------------|-------------------|
| **Orchestrator** | Plans research, delegates tasks, coordinates results | — | Retries failed agents with broadened search terms |
| **Literature Scout** | Searches PubMed via NCBI Entrez API | PubMed MCP | Falls back to broader query if no results |
| **PDF Indexer** | Downloads + chunks open-access full texts from PMC | Cloud Storage MCP | Gracefully continues in abstract-only mode |
| **Risk Analyst** | Extracts SHAP-style ranked risk factors from literature | Vertex AI MCP | Returns partial results if JSON parse fails |
| **Synthesizer** | Merges findings into structured evidence summary | — | Returns raw text if JSON structure fails |
| **Safety Guard** | LLM-as-a-Judge: validates citations, blocks hallucinations | — | Passes through with warning if validation fails |
| **Report Builder** | Generates final clinical brief with evidence grades | — | Falls back to plain text report |

---

## Tech Stack

- **Agent Framework:** Google ADK (`google-adk`) with `LlmAgent`
- **LLM:** Gemini 2.0 Flash
- **MCP Servers:** Custom FastAPI servers wrapping PubMed, Google Cloud Storage, Vertex AI
- **Backend:** FastAPI + Server-Sent Events for real-time log streaming
- **Frontend:** React 18 + Vite + Tailwind CSS
- **Deployment:** Google Cloud Run (asia-southeast1)

---

## Setup Instructions

### Prerequisites
- Python 3.11+
- Node.js 20+
- Google Cloud account with billing enabled
- Google AI Studio API key (for Gemini)

### Local Development

```bash
# Clone
git clone https://github.com/YOUR_USERNAME/mediswarm
cd mediswarm

# Backend
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys

uvicorn main:app --reload --port 8000

# Frontend (separate terminal)
cd app
npm install
npm run dev
# Open http://localhost:5173
```

### Environment Variables

```env
GOOGLE_API_KEY=           # Google AI Studio key
GOOGLE_CLOUD_PROJECT=     # GCP project ID
GOOGLE_CLOUD_REGION=asia-southeast1
GCS_BUCKET_NAME=mediswarm-pdf-cache
NCBI_EMAIL=               # Required for PubMed API
NCBI_API_KEY=             # Optional, increases rate limits
```

### Cloud Run Deployment

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
gcloud services enable run.googleapis.com cloudbuild.googleapis.com
gcloud builds submit --config cloudbuild.yaml
```

---

## Judging Criteria Alignment

| Criterion | Weight | Implementation |
|-----------|--------|----------------|
| Agentic Agency & Recovery | 40% | Orchestrator retries with broadened terms; PDF indexer falls back to abstract-only mode; all agents emit reasoning traces visible in the UI log stream |
| Technical Depth (ADK/MCP) | 30% | 7 ADK `LlmAgent` instances; 3 custom MCP servers (PubMed, Cloud Storage, Vertex AI); proper A2A message passing |
| System Robustness | 20% | Safety Guard runs LLM-as-a-Judge on all outputs; hallucinated citations are blocked; graceful degradation at every layer |
| Docs & Demo | 10% | This README; 150-second demo video showing live agent logs |

---

## Research Context

This project was inspired by published research on explainable AI for diabetic readmission prediction, specifically SHAP-based risk stratification on the UCI Diabetes 130-US Hospitals dataset. MediSwarm extends this by creating a living literature intelligence layer — automatically synthesizing new evidence as it is published on PubMed.

---

## Rules Compliance

- ✅ Solo submission
- ✅ Original work — no plagiarism
- ✅ API keys stored in environment variables only (never committed)
- ✅ GDG Community Code of Conduct followed
- ✅ Demo video uploaded as YouTube Unlisted

---

*Built for Gemini Nexus: The Agentverse Hackathon, March 14–15, 2026*
