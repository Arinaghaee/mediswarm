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
  idle:            { dot: 'bg-[#2a2a3a]',   text: 'text-[#475569]',  label: 'idle' },
  agent_start:     { dot: 'bg-amber-500',    text: 'text-amber-400',  label: 'starting' },
  agent_thinking:  { dot: 'bg-amber-400 animate-pulse', text: 'text-amber-300', label: 'thinking' },
  agent_done:      { dot: 'bg-emerald-500',  text: 'text-emerald-400', label: 'done' },
  swarm_complete:  { dot: 'bg-emerald-500',  text: 'text-emerald-400', label: 'done' },
  agent_failed:    { dot: 'bg-red-500',      text: 'text-red-400',    label: 'failed' },
  error:           { dot: 'bg-red-500',      text: 'text-red-400',    label: 'error' },
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
