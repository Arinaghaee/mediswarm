# MediSwarm — Claude Code Session Prompt

Paste this entire block into Claude Code to start your build session.

---

## PASTE THIS INTO CLAUDE CODE:

```
I am building MediSwarm for a 24-hour hackathon (Gemini Nexus: The Agentverse, Track A: Intelligence Bureau). 
I have 5 spec files that define the complete system. Build everything in order.

My project is a multi-agent medical research swarm using Google ADK + Gemini + MCP tools. 
It answers clinical questions about diabetic readmission by coordinating 7 specialized agents 
that search PubMed, index PDFs, extract risk factors, and produce clinical briefs.

## TASK: Build the complete project

Read and implement these spec files in order:

1. Read CLAUDE.md — master spec with repo structure and constraints
2. Read SPEC_backend.md — implement main.py and requirements.txt
3. Read SPEC_agents.md — implement all 7 agents in /agents/
4. Read SPEC_frontend.md — implement the React app in /app/
5. Read SPEC_deploy.md — implement Dockerfile, cloudbuild.yaml, .env.example
6. Read SPEC_readme.md — generate README.md

## After implementing each file:
- Verify imports are consistent across files
- Check that agents/__init__.py exports the emit() helper correctly
- Ensure every agent imports emit from agents/__init__.py
- Make sure main.py correctly imports run_swarm from agents/orchestrator.py
- Verify CORS is enabled in FastAPI
- Confirm the React proxy config points to localhost:8000

## After all files are built, do these checks:
1. Run: pip install -r requirements.txt (verify no conflicts)
2. Run: cd app && npm install (verify no conflicts)
3. Run: python -c "from agents.orchestrator import run_swarm; print('imports ok')"
4. Report any issues found and fix them

## Environment setup reminder:
- Never hardcode API keys
- Use os.environ.get() everywhere
- The .env file should not be committed (add to .gitignore)

Start now. Read CLAUDE.md first.
```
