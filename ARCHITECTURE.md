# MediSwarm — Architecture Diagram

Full end-to-end flow from user query to clinical brief.

```mermaid
flowchart TD
    User(["🧑‍⚕️ Clinician\n(Browser)"])

    subgraph Frontend ["React Frontend (Vite + Tailwind)"]
        QI["QueryInput\nUser types clinical question"]
        ALS["AgentLogStream\nLive SSE event feed"]
        AC["AgentCard\nPer-agent status dots\nidle → thinking → done"]
        CB["ClinicalBrief\nFinal structured report"]
    end

    subgraph Backend ["FastAPI Backend"]
        POST["POST /api/query\nCreate session + asyncio.Task"]
        SSE["GET /api/stream/{session_id}\nServer-Sent Events generator"]
        STOP["POST /api/stop/{session_id}\nCancel task + push terminal event"]
        SESSIONS[("sessions{}\nIn-memory session store\n(queue, task, result)")]
    end

    subgraph Orchestrator ["Orchestrator Agent"]
        PLAN["1. Build research plan\nGemini → JSON\n(search_terms, population,\nevidence_priority)"]
        DELEGATE["2. Emit: Delegating to\nliterature_scout + pdf_indexer\nin parallel"]
        GATHER["3. asyncio.gather()\nwait for both tasks"]
        RETRY["4. Retry logic\n(max 1 retry per agent)\nbroader terms on 400"]
        PHASE2["5. Phase 2: Risk Analysis"]
        PHASE3["6. Phase 3: Synthesis"]
        PHASE4["7. Phase 4: Safety + Report"]
    end

    subgraph Phase1 ["Phase 1 — Parallel Data Gathering"]
        direction LR

        subgraph LitScout ["Literature Scout"]
            LS1["Clean search term\n(strip OR / quotes)"]
            LS2["Entrez.esearch\nPubMed, retmax=10"]
            LS3["Entrez.efetch\nabstracts as XML"]
            LS4["Parse PubmedArticle\nrecords → papers[]"]
            LS5["Emit: Top 3 titles found"]
        end

        subgraph PDFIdx ["PDF Indexer"]
            PI1["Build PMC query\n+ open access filter"]
            PI2["Entrez.esearch\nPubMed Central"]
            PI3["Entrez.efetch\nfull XML for top 3"]
            PI4["Strip HTML tags\nChunk into 500-char blocks"]
        end
    end

    subgraph Phase2 ["Phase 2 — Risk Analysis"]
        RA1["Build context from\ntop 6 paper abstracts"]
        RA2["Gemini prompt:\nextract + rank risk factors\nwith importance scores"]
        RA3["Parse JSON response\n(risk_factors[], protective_factors[])"]
        RA4["Emit per factor:\nIdentified: X (importance: Y)"]
    end

    subgraph Phase3 ["Phase 3 — Evidence Synthesis"]
        SY1["Merge top 5 risks\n+ top 3 protective factors"]
        SY2["Gemini prompt:\nsynthesize with evidence grades A/B/C"]
        SY3["Parse JSON response\n(key_findings[], recommendations[])"]
        SY4["Emit: evidence grade assigned\n+ N findings merged"]
    end

    subgraph Phase4 ["Phase 4 — Safety + Report"]
        subgraph SafetyGuard ["Safety Guard (LLM-as-a-Judge)"]
            SG1["Pattern scan:\nfake DOIs, null PMIDs"]
            SG2["Emit: Checking N citations...\nno hallucinated DOIs detected"]
            SG3["Gemini judge prompt:\ncheck stats, unsafe claims,\nguideline contradictions"]
            SG4["If is_safe=True\n+ score=0/None → set score=0.95"]
        end

        subgraph ReportBuilder ["Report Builder"]
            RB1["Gemini prompt:\nformat full clinical brief"]
            RB2["Parse JSON report\n(title, risk_factors,\nrecommendations, markdown)"]
        end
    end

    NCBI[("NCBI / PubMed\nEntrez API")]
    PMC[("PubMed Central\nOpen-Access Full Text")]
    GEMINI[("Gemini 2.5 Flash\ngoogle-genai SDK")]

    %% User → Frontend → Backend
    User -->|"types query\n⌘+Enter or button"| QI
    QI -->|"axios POST"| POST
    POST -->|"create session\ncreate asyncio.Task"| SESSIONS
    POST -->|"session_id"| QI
    QI -->|"open EventSource"| SSE
    SSE -->|"reads from queue"| SESSIONS
    SSE -->|"SSE events stream"| ALS
    ALS --> AC
    User -->|"Stop button"| STOP
    STOP -->|"task.cancel()\npush error event"| SESSIONS

    %% Backend → Orchestrator
    SESSIONS -->|"run_swarm(query)"| PLAN

    %% Orchestrator flow
    PLAN -->|"Gemini"| GEMINI
    PLAN --> DELEGATE
    DELEGATE --> GATHER
    GATHER --> Phase1
    Phase1 --> RETRY
    RETRY --> PHASE2
    PHASE2 --> Phase2
    Phase2 --> PHASE3
    PHASE3 --> Phase3
    Phase3 --> PHASE4
    PHASE4 --> Phase4

    %% Phase 1 internals
    LS1 --> LS2 --> LS3 --> LS4 --> LS5
    PI1 --> PI2 --> PI3 --> PI4

    %% External calls
    LS2 -->|"HTTP"| NCBI
    LS3 -->|"HTTP"| NCBI
    PI2 -->|"HTTP"| PMC
    PI3 -->|"HTTP"| PMC
    RA2 -->|"generate_content"| GEMINI
    SY2 -->|"generate_content"| GEMINI
    SG3 -->|"generate_content"| GEMINI
    RB1 -->|"generate_content"| GEMINI

    %% Phase internals
    RA1 --> RA2 --> RA3 --> RA4
    SY1 --> SY2 --> SY3 --> SY4
    SG1 --> SG2 --> SG3 --> SG4
    RB1 --> RB2

    %% Final output
    RB2 -->|"swarm_complete event\n+ report JSON"| SESSIONS
    SESSIONS -->|"SSE: swarm_complete"| CB
    CB -->|"renders brief"| User

    %% Styling
    classDef agent fill:#1e1b4b,stroke:#6d28d9,color:#e2e8f0
    classDef external fill:#0f172a,stroke:#475569,color:#94a3b8
    classDef frontend fill:#0c1a2e,stroke:#1d4ed8,color:#93c5fd
    classDef backend fill:#0f1a1a,stroke:#0f766e,color:#99f6e4
    classDef decision fill:#1a0f0f,stroke:#b45309,color:#fcd34d

    class LitScout,PDFIdx,Phase2,Phase3,SafetyGuard,ReportBuilder,Orchestrator agent
    class NCBI,PMC,GEMINI external
    class Frontend,QI,ALS,AC,CB frontend
    class Backend,POST,SSE,STOP,SESSIONS backend
```

## Agent Responsibility Summary

| Agent | Input | Output | LLM call |
|-------|-------|--------|-----------|
| **Orchestrator** | user query | research plan + coordination | yes — plan |
| **Literature Scout** | search terms | papers[] with abstracts | no (Entrez) |
| **PDF Indexer** | search terms | text chunks[] from PMC | no (Entrez) |
| **Risk Analyst** | papers + chunks | ranked risk_factors[] | yes |
| **Synthesizer** | risk factors + papers | key_findings[], recommendations[] | yes |
| **Safety Guard** | synthesis JSON | validated synthesis + safety_score | yes (judge) |
| **Report Builder** | validated synthesis | final clinical brief JSON | yes |

## SSE Event Types

| Event | Trigger | Frontend effect |
|-------|---------|-----------------|
| `agent_start` | agent begins | amber dot, "starting" label |
| `agent_thinking` | agent emits reasoning | amber pulse dot, message preview |
| `agent_done` | agent finishes | green dot, "done" label |
| `swarm_complete` | full pipeline done | orchestrator turns green, brief renders |
| `error` | any failure or user stop | red dot, stream closes |
