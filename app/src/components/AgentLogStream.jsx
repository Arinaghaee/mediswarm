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
