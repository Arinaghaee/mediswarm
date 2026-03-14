const STATUS_STYLES = {
  idle:     'text-[#475569] bg-[#2a2a3a] border-[#2a2a3a]',
  running:  'text-amber-400 bg-amber-400/10 border-amber-500/20',
  complete: 'text-emerald-400 bg-emerald-400/10 border-emerald-500/20',
  error:    'text-red-400 bg-red-400/10 border-red-500/20',
  thinking: 'text-yellow-300 bg-yellow-400/10 border-yellow-500/20',
  done:     'text-emerald-400 bg-emerald-400/10 border-emerald-500/20',
  failed:   'text-red-400 bg-red-400/10 border-red-500/20',
}

const STATUS_DOTS = {
  idle:     'bg-[#475569]',
  running:  'bg-amber-400 animate-pulse',
  complete: 'bg-emerald-400',
  error:    'bg-red-400',
  thinking: 'bg-yellow-300 animate-pulse',
  done:     'bg-emerald-400',
  failed:   'bg-red-400',
}

export default function StatusBadge({ status, label }) {
  const style = STATUS_STYLES[status] || STATUS_STYLES.idle
  const dot = STATUS_DOTS[status] || STATUS_DOTS.idle
  const displayLabel = label || status

  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-mono px-2 py-0.5 rounded border ${style}`}>
      <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${dot}`} />
      {displayLabel}
    </span>
  )
}
