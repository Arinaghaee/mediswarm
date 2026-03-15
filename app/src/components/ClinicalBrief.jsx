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
                    {rec.strength} · {rec.rationale}
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
