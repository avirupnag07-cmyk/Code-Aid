import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { EmptyState, ErrorNotice, PageIntro, StatusPill } from '../components/AppShell'
import { api, formatRelativeDate } from '../lib/api'
import type { InvestigationSummary } from '../lib/types'

export function DashboardPage() {
  const [investigations, setInvestigations] = useState<InvestigationSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    api.investigations().then(setInvestigations).catch((cause: Error) => setError(cause.message)).finally(() => setLoading(false))
  }, [])

  const stats = useMemo(() => ({ total: investigations.length, active: investigations.filter((item) => item.status.includes('test') || item.status === 'analyzed').length, findings: investigations.reduce((sum, item) => sum + item.finding_count, 0) }), [investigations])

  return <>
    <PageIntro eyebrow="INVESTIGATION DESK" title="Good morning, engineer." description="A focused workspace for turning bug reports into reproducible evidence." action={<Link className="button button--primary" to="/app/new">＋ New investigation</Link>} />
    {error && <ErrorNotice message={error} onDismiss={() => setError('')} />}
     <div className="metric-strip"><Metric label="Investigations" value={String(stats.total).padStart(2, '0')} detail="stored locally" /><Metric label="Awaiting review" value={String(stats.active).padStart(2, '0')} detail="analysis available" /><Metric label="Findings" value={String(stats.findings).padStart(2, '0')} detail="with evidence" /><div className="metric-status"><span className="status-dot" /><span>Local engine<br /><strong>ready</strong></span></div></div>
    <section className="workspace-panel investigations-panel"><div className="panel-heading"><div><span className="panel-kicker">RECENT WORK</span><h2>Investigations</h2></div><span className="panel-count">{investigations.length} total</span></div>
        {loading ? <LoadingRows /> : investigations.length === 0 ? <EmptyState title="Your desk is clear." description="Upload a project ZIP with an error report to start an auditable local investigation." action={<Link className="button button--outline" to="/app/new">Create first investigation <span>↗</span></Link>} /> : <div className="investigation-table"><div className="table-head"><span>Investigation</span><span>Status</span><span>Findings</span><span>Last activity</span><span /></div>{investigations.map((item) => <InvestigationRow item={item} key={item.id} />)}</div>}
    </section>
      <section className="dashboard-lower"><div className="workspace-panel quick-start"><div className="panel-kicker">QUICK START</div><h2>Bring the failure with you.</h2><p>Upload a ZIP containing the project source and a traceback file. Code-Aid inspects the archive as data before analysis.</p><div className="quick-links"><Link to="/app/new">Upload a project ZIP <span>→</span></Link><Link to="/docs#security">Review upload safety <span>→</span></Link></div></div><div className="workspace-panel boundary-card"><div className="boundary-mark">⌁</div><div><div className="panel-kicker">RUNTIME BOUNDARY</div><h3>Analysis never needs a model key.</h3><p>Generated tests only run through the Docker boundary. If it is unavailable, the result says so.</p><Link className="text-link" to="/docs#security">Review safety notes ↗</Link></div></div></section>
  </>
}

function Metric({ label, value, detail }: { label: string; value: string; detail: string }) { return <div className="metric"><span>{label}</span><strong>{value}</strong><small>{detail}</small></div> }
function LoadingRows() { return <div className="loading-rows">{[1, 2, 3].map((row) => <div className="loading-row" key={row}><span /><span /><span /><span /></div>)}</div> }
function InvestigationRow({ item }: { item: InvestigationSummary }) { return <Link className="investigation-row" to={`/app/investigations/${item.id}`}><div className="investigation-title"><span className="row-glyph">◌</span><div><strong>{item.title}</strong><small>{item.source_type}{item.sample_id ? ` / ${item.sample_id}` : ''}</small></div></div><StatusPill value={item.status} /><span className="table-number">{item.finding_count.toString().padStart(2, '0')}</span><span className="table-date">{formatRelativeDate(item.updated_at)}</span><span className="row-arrow">↗</span></Link> }
