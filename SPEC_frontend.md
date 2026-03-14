# SPEC: React Frontend

## Setup

```bash
cd app
npm create vite@latest . -- --template react
npm install
npm install tailwindcss @tailwindcss/vite axios react-markdown
```

`vite.config.js`:
```js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { proxy: { '/api': 'http://localhost:8000' } }
})
```

---

## Design System

Dark theme. Colors:
- Background: `#0a0a0f` (near black)
- Surface: `#12121a`
- Card: `#1a1a26`
- Border: `#2a2a3a`
- Primary: `#7c3aed` (purple — ADK brand)
- Accent: `#10b981` (green — success/done)
- Warning: `#f59e0b` (amber — thinking)
- Danger: `#ef4444` (red — failed)
- Text primary: `#f1f5f9`
- Text secondary: `#94a3b8`
- Text muted: `#475569`

Font: System monospace for agent logs. Sans-serif for UI.

---

## File: `app/src/App.jsx`

```jsx
import { useState, useRef, useCallback } from 'react'
import QueryInput from './components/QueryInput'
import AgentLogStream from './components/AgentLogStream'
import ClinicalBrief from './components/ClinicalBrief'
import axios from 'axios'

const EXAMPLE_QUERIES = [
  "What reduces 30-day diabetic readmission in elderly patients?",
  "Which interventions most effectively prevent T2D readmission in low-income populations?",
  "What are the strongest predictors of 30-day readmission after diabetic ketoacidosis?",
]

export default function App() {
  const [query, setQuery] = useState('')
  const [sessionId, setSessionId] = useState(null)
  const [events, setEvents] = useState([])
  const [report, setReport] = useState(null)
  const [status, setStatus] = useState('idle') // idle | running | complete | error
  const [agentStates, setAgentStates] = useState({})
  const eventSourceRef = useRef(null)

  const updateAgentState = useCallback((agent, state, message) => {
    setAgentStates(prev => ({
      ...prev,
      [agent]: { state, message, updatedAt: new Date() }
    }))
  }, [])

  const handleSubmit = async (q) => {
    if (!q.trim() || status === 'running') return

    setStatus('running')
    setEvents([])
    setReport(null)
    setAgentStates({})

    try {
      const res = await axios.post('/api/query', { query: q })
      const sid = res.data.session_id
      setSessionId(sid)

      // Open SSE stream
      const es = new EventSource(`/api/stream/${sid}`)
      eventSourceRef.current = es

      es.onmessage = (e) => {
        const event = JSON.parse(e.data)
        setEvents(prev => [...prev, event])

        updateAgentState(event.agent, event.type, event.message)

        if (event.type === 'swarm_complete') {
          setReport(event.data?.report)
          setStatus('complete')
          es.close()
        }
        if (event.type === 'error') {
          setStatus('error')
          es.close()
        }
      }

      es.onerror = () => {
        setStatus('error')
        es.close()
      }
    } catch (err) {
      setStatus('error')
      setEvents(prev => [...prev, {
        type: 'error', agent: 'system',
        message: `Connection failed: ${err.message}`,
        timestamp: new Date().toISOString(), data: {}
      }])
    }
  }

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-[#f1f5f9]">
      {/* Header */}
      <header className="border-b border-[#2a2a3a] px-6 py-4 flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-purple-600 flex items-center justify-center text-white font-bold text-sm">M</div>
        <div>
          <h1 className="font-semibold text-white tracking-tight">MediSwarm</h1>
          <p className="text-xs text-[#475569]">Diabetic Readmission Research Intelligence</p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <span className="text-xs text-[#475569]">Powered by</span>
          <span className="text-xs font-mono text-purple-400">Google ADK + Gemini</span>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-6 py-8 grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left column: Input + Agent stream */}
        <div className="flex flex-col gap-6">
          <QueryInput
            query={query}
            setQuery={setQuery}
            onSubmit={handleSubmit}
            status={status}
            examples={EXAMPLE_QUERIES}
          />
          <AgentLogStream
            events={events}
            agentStates={agentStates}
            status={status}
          />
        </div>

        {/* Right column: Clinical brief */}
        <div>
          <ClinicalBrief report={report} status={status} query={query} />
        </div>
      </div>
    </div>
  )
}
```

---

## File: `app/src/components/QueryInput.jsx`

```jsx
export default function QueryInput({ query, setQuery, onSubmit, status, examples }) {
  return (
    <div className="bg-[#12121a] rounded-xl border border-[#2a2a3a] p-5">
      <label className="text-xs font-mono text-purple-400 uppercase tracking-widest mb-3 block">
        Clinical Query
      </label>
      <textarea
        value={query}
        onChange={e => setQuery(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter' && e.metaKey) onSubmit(query) }}
        placeholder="e.g. What reduces 30-day diabetic readmission in elderly patients?"
        rows={3}
        disabled={status === 'running'}
        className="w-full bg-[#0a0a0f] border border-[#2a2a3a] rounded-lg px-4 py-3 text-sm text-[#f1f5f9] placeholder-[#475569] resize-none focus:outline-none focus:border-purple-500 disabled:opacity-50 transition-colors"
      />
      <div className="flex gap-2 mt-3 flex-wrap">
        {examples.map((ex, i) => (
          <button key={i} onClick={() => setQuery(ex)}
            className="text-xs text-[#475569] hover:text-purple-400 border border-[#2a2a3a] hover:border-purple-500/40 rounded px-2 py-1 transition-colors truncate max-w-[200px]">
            {ex.substring(0, 40)}...
          </button>
        ))}
      </div>
      <button
        onClick={() => onSubmit(query)}
        disabled={!query.trim() || status === 'running'}
        className="mt-4 w-full bg-purple-600 hover:bg-purple-700 disabled:opacity-40 disabled:cursor-not-allowed text-white font-medium rounded-lg py-2.5 text-sm transition-colors flex items-center justify-center gap-2"
      >
        {status === 'running' ? (
          <>
            <span className="inline-block w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin"/>
            Swarm running...
          </>
        ) : 'Launch Agent Swarm →'}
      </button>
    </div>
  )
}
```

---

## File: `app/src/components/AgentCard.jsx`

```jsx
const AGENTS = [
  { id: 'orchestrator', label: 'Orchestrator', icon: '⬡' },
  { id: 'literature_scout', label: 'Literature Scout', icon: '◎' },
  { id: 'pdf_indexer', label: 'PDF Indexer', icon: '▦' },
  { id: 'risk_analyst', label: 'Risk Analyst', icon: '◈' },
  { id: 'synthesizer', label: 'Synthesizer', icon: '◉' },
  { id: 'safety_guard', label: 'Safety Guard', icon: '◆' },
  { id: 'report_builder', label: 'Report Builder', icon: '◧' },
]

const STATE_STYLES = {
  idle:           { dot: 'bg-[#2a2a3a]',   text: 'text-[#475569]',  label: 'idle' },
  agent_start:    { dot: 'bg-amber-500',    text: 'text-amber-400',  label: 'starting' },
  agent_thinking: { dot: 'bg-amber-400 animate-pulse', text: 'text-amber-300', label: 'thinking' },
  agent_done:     { dot: 'bg-emerald-500',  text: 'text-emerald-400', label: 'done' },
  agent_failed:   { dot: 'bg-red-500',      text: 'text-red-400',    label: 'failed' },
  error:          { dot: 'bg-red-500',      text: 'text-red-400',    label: 'error' },
}

export default function AgentCard({ agentStates }) {
  return (
    <div className="grid grid-cols-2 gap-2">
      {AGENTS.map(agent => {
        const s = agentStates[agent.id]
        const style = STATE_STYLES[s?.state] || STATE_STYLES.idle
        return (
          <div key={agent.id}
            className="bg-[#0a0a0f] border border-[#2a2a3a] rounded-lg px-3 py-2 flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full flex-shrink-0 ${style.dot}`}/>
            <div className="min-w-0 flex-1">
              <div className="text-xs font-medium text-[#94a3b8] truncate">{agent.label}</div>
              <div className={`text-xs truncate ${style.text}`}>
                {s?.message ? s.message.substring(0, 36) + (s.message.length > 36 ? '...' : '') : style.label}
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}
```

---

## File: `app/src/components/AgentLogStream.jsx`

```jsx
import { useEffect, useRef } from 'react'
import AgentCard from './AgentCard'

const EVENT_COLORS = {
  agent_start:    'text-amber-400',
  agent_thinking: 'text-yellow-300',
  agent_done:     'text-emerald-400',
  agent_failed:   'text-red-400',
  swarm_complete: 'text-purple-400',
  error:          'text-red-500',
}

const AGENT_TAGS = {
  orchestrator:     '[ORCH]',
  literature_scout: '[LIT] ',
  pdf_indexer:      '[PDF] ',
  risk_analyst:     '[RISK]',
  synthesizer:      '[SYN] ',
  safety_guard:     '[SAFE]',
  report_builder:   '[RPT] ',
  system:           '[SYS] ',
}

export default function AgentLogStream({ events, agentStates, status }) {
  const logRef = useRef(null)

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight
    }
  }, [events])

  return (
    <div className="bg-[#12121a] rounded-xl border border-[#2a2a3a] p-5 flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <label className="text-xs font-mono text-purple-400 uppercase tracking-widest">
          Agent Thinking Log
        </label>
        <span className={`text-xs font-mono px-2 py-0.5 rounded ${
          status === 'running'  ? 'text-amber-400 bg-amber-400/10' :
          status === 'complete' ? 'text-emerald-400 bg-emerald-400/10' :
          status === 'error'    ? 'text-red-400 bg-red-400/10' :
          'text-[#475569] bg-[#2a2a3a]'
        }`}>
          {status}
        </span>
      </div>

      {/* Agent status grid */}
      <AgentCard agentStates={agentStates} />

      {/* Log output */}
      <div
        ref={logRef}
        className="bg-[#0a0a0f] rounded-lg border border-[#2a2a3a] p-3 h-64 overflow-y-auto font-mono text-xs leading-relaxed"
      >
        {events.length === 0 ? (
          <div className="text-[#475569] italic">Waiting for swarm to launch...</div>
        ) : events.map((ev, i) => (
          <div key={i} className="flex gap-2 mb-1">
            <span className="text-[#2a2a3a] flex-shrink-0">
              {new Date(ev.timestamp).toISOString().substring(11,19)}
            </span>
            <span className="text-[#475569] flex-shrink-0">
              {AGENT_TAGS[ev.agent] || '[???]'}
            </span>
            <span className={EVENT_COLORS[ev.type] || 'text-[#94a3b8]'}>
              {ev.message}
            </span>
          </div>
        ))}
        {status === 'running' && (
          <div className="flex gap-1 mt-1">
            <span className="text-purple-400 animate-pulse">▋</span>
          </div>
        )}
      </div>
    </div>
  )
}
```

---

## File: `app/src/components/ClinicalBrief.jsx`

```jsx
import ReactMarkdown from 'react-markdown'

const GRADE_COLORS = {
  A: 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10',
  B: 'text-amber-400 border-amber-500/30 bg-amber-500/10',
  C: 'text-[#94a3b8] border-[#2a2a3a] bg-[#2a2a3a]',
}

export default function ClinicalBrief({ report, status, query }) {
  if (!report && status === 'idle') return (
    <div className="bg-[#12121a] rounded-xl border border-[#2a2a3a] p-8 flex flex-col items-center justify-center min-h-[400px] text-center">
      <div className="text-4xl mb-4 opacity-20">⬡</div>
      <p className="text-[#475569] text-sm">Clinical brief will appear here after the swarm completes.</p>
    </div>
  )

  if (!report && status === 'running') return (
    <div className="bg-[#12121a] rounded-xl border border-[#2a2a3a] p-8 flex flex-col items-center justify-center min-h-[400px] text-center">
      <div className="w-8 h-8 border-2 border-purple-500/30 border-t-purple-500 rounded-full animate-spin mb-4"/>
      <p className="text-[#475569] text-sm">Agents are working...</p>
    </div>
  )

  if (!report) return null

  return (
    <div className="bg-[#12121a] rounded-xl border border-[#2a2a3a] p-5 flex flex-col gap-5 max-h-[90vh] overflow-y-auto">
      {/* Header */}
      <div className="border-b border-[#2a2a3a] pb-4">
        <div className="text-xs font-mono text-purple-400 uppercase tracking-widest mb-1">Clinical Brief</div>
        <h2 className="text-sm font-semibold text-white leading-snug">{report.title}</h2>
        <p className="text-xs text-[#475569] mt-1">
          {report.evidence_summary?.papers_reviewed} papers reviewed ·{' '}
          Evidence quality: <span className="text-amber-400">{report.evidence_summary?.evidence_quality}</span>
        </p>
      </div>

      {/* Executive summary */}
      <div>
        <div className="text-xs text-[#475569] uppercase tracking-wider mb-2">Summary</div>
        <p className="text-sm text-[#94a3b8] leading-relaxed">{report.executive_summary}</p>
      </div>

      {/* Risk factors */}
      {report.risk_factors?.length > 0 && (
        <div>
          <div className="text-xs text-[#475569] uppercase tracking-wider mb-2">Key Risk Factors</div>
          <div className="flex flex-col gap-2">
            {report.risk_factors.slice(0, 6).map((rf, i) => (
              <div key={i} className="flex items-start gap-3 bg-[#0a0a0f] rounded-lg px-3 py-2.5">
                <span className={`text-xs font-mono border rounded px-1.5 py-0.5 flex-shrink-0 ${GRADE_COLORS[rf.evidence_grade] || GRADE_COLORS.C}`}>
                  {rf.evidence_grade || 'C'}
                </span>
                <div>
                  <div className="text-xs font-medium text-[#f1f5f9]">{rf.factor}</div>
                  <div className="text-xs text-[#475569] mt-0.5">{rf.recommendation}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recommendations */}
      {report.clinical_recommendations?.length > 0 && (
        <div>
          <div className="text-xs text-[#475569] uppercase tracking-wider mb-2">Recommendations</div>
          <div className="flex flex-col gap-2">
            {report.clinical_recommendations.slice(0, 4).map((rec, i) => (
              <div key={i} className="flex gap-3 bg-[#0a0a0f] rounded-lg px-3 py-2.5">
                <span className="text-xs text-purple-400 font-mono flex-shrink-0">{i + 1}.</span>
                <div>
                  <div className="text-xs font-medium text-[#f1f5f9]">{rec.action}</div>
                  <div className="text-xs text-[#475569] mt-0.5">
                    {rec.strength} · {rec.rationale?.substring(0, 80)}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Disclaimer */}
      <div className="border-t border-[#2a2a3a] pt-3">
        <p className="text-xs text-[#2a2a3a]">{report.disclaimer}</p>
      </div>
    </div>
  )
}
```

---

## File: `app/src/index.css`

```css
@import "tailwindcss";

* { box-sizing: border-box; }
body { margin: 0; font-family: system-ui, -apple-system, sans-serif; }

::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: #0a0a0f; }
::-webkit-scrollbar-thumb { background: #2a2a3a; border-radius: 2px; }
```
