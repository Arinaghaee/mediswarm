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

  const handleStop = useCallback(async () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
    if (sessionId) {
      try { await axios.post(`/api/stop/${sessionId}`) } catch (_) {}
    }
    setStatus('idle')
    setEvents(prev => [...prev, {
      type: 'error', agent: 'system',
      message: 'Stopped by user.',
      timestamp: new Date().toISOString(), data: {}
    }])
  }, [sessionId])

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
            onStop={handleStop}
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
