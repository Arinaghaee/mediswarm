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
