import { FormEvent, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { CodeBlock, EmptyState, ErrorNotice, PageIntro, StatusPill } from '../components/AppShell'
import { api, formatDate, formatRelativeDate } from '../lib/api'
import type { Evidence, Finding, Investigation, VerificationResult } from '../lib/types'

type Tab = 'overview' | 'source' | 'tests' | 'verification'

export function InvestigationPage() {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const [investigation, setInvestigation] = useState<Investigation | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [tab, setTab] = useState<Tab>('overview')
  const [running, setRunning] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [patchPath, setPatchPath] = useState('')
  const [patchContent, setPatchContent] = useState('')
  const [verification, setVerification] = useState<VerificationResult | null>(null)
  const [verifying, setVerifying] = useState(false)

  useEffect(() => { api.investigation(id).then(setInvestigation).catch((cause: Error) => setError(cause.message)).finally(() => setLoading(false)) }, [id])
  const topFinding = useMemo(() => investigation?.results.findings.find((finding) => finding.severity === 'high') || investigation?.results.findings[0], [investigation])
  if (loading) return <div className="loading-detail"><div className="loading-orbit" /><p>Loading investigation record…</p></div>
  if (error || !investigation) return <><ErrorNotice message={error || 'Investigation not found.'} /><Link className="text-link" to="/app">← Return to desk</Link></>

  async function runTests() { setRunning(true); setError(''); try { const result = await api.runTests(id); setInvestigation(result); setTab('tests') } catch (cause) { setError(cause instanceof Error ? cause.message : 'Tests could not be started.') } finally { setRunning(false) } }
  async function deleteInvestigation() { if (!window.confirm('Delete this investigation and its stored source files? This cannot be undone.')) return; setDeleting(true); try { await api.deleteInvestigation(id); navigate('/app') } catch (cause) { setError(cause instanceof Error ? cause.message : 'The investigation could not be deleted.'); setDeleting(false) } }
  async function verifyPatch(event: FormEvent) { event.preventDefault(); setVerifying(true); setError(''); try { const result = await api.verifyPatch(id, patchPath, patchContent); setVerification(result.verification); setInvestigation(result); setTab('verification') } catch (cause) { setError(cause instanceof Error ? cause.message : 'Patch verification failed.') } finally { setVerifying(false) } }

  return <>
    <div className="detail-back"><Link to="/app">← All investigations</Link><span>/</span><span>{investigation.source.sample_id || 'uploaded project'}</span></div>
     <PageIntro eyebrow="INVESTIGATION RECORD" title={investigation.title} description={`${investigation.source.file_count} source files · ${detectedLanguage(investigation)} · created ${formatDate(investigation.created_at)}`} action={<div className="detail-actions"><StatusPill value={investigation.status} /><a className="button button--outline" href={api.reportUrl(id)} download>Export report ↓</a><button className="icon-button delete-button" onClick={deleteInvestigation} disabled={deleting} aria-label="Delete investigation">⌫</button></div>} />
    {error && <ErrorNotice message={error} onDismiss={() => setError('')} />}
     <div className="diagnostic-banner"><div className="diagnostic-signal"><span className="signal-pulse" /><span>OBSERVED FAILURE</span></div><div className="diagnostic-error"><strong>{String(investigation.source.metadata.exception_type || topFinding?.rule_id || 'Reported error')}</strong><span>{investigation.source.traceback.split('\n').filter(Boolean).at(-1) || 'Error details supplied by the reporter'}</span></div><div className="diagnostic-meta"><span>source: <strong>{investigation.source.source_type}</strong></span><span>language: <strong>{detectedLanguage(investigation)}</strong></span><span>analysis: <strong>deterministic</strong></span></div></div>
     <InvestigationWorkflow investigation={investigation} onSelect={(nextTab) => setTab(nextTab)} />
    <nav className="detail-tabs" aria-label="Investigation sections">{([['overview', 'Overview'], ['source', 'Source evidence'], ['tests', `Generated tests (${investigation.results.generated_tests.length})`], ['verification', 'Patch verification']] as const).map(([value, label]) => <button className={tab === value ? 'active' : ''} key={value} onClick={() => setTab(value)}>{label}</button>)}</nav>
    {tab === 'overview' && <Overview investigation={investigation} onRunTests={runTests} running={running} onOpenSource={() => setTab('source')} />}
    {tab === 'source' && <SourceEvidence investigation={investigation} />}
    {tab === 'tests' && <TestsPanel investigation={investigation} onRunTests={runTests} running={running} />}
    {tab === 'verification' && <VerificationPanel investigation={investigation} patchPath={patchPath} setPatchPath={setPatchPath} patchContent={patchContent} setPatchContent={setPatchContent} onSubmit={verifyPatch} verifying={verifying} verification={verification || investigation.results.verification} />}
  </>
}

function detectedLanguage(investigation: Investigation): string {
  const metadata = investigation.source.metadata || {}
  const configured = investigation.source.detected_languages?.[0] || investigation.results.detected_languages?.[0] || metadata.detected_language || metadata.language || metadata.language_name
  if (typeof configured === 'string' && configured.trim()) return configured
  const extensions = investigation.source.files.map((file) => file.path.toLowerCase().split('.').pop()).filter(Boolean)
  if (extensions.includes('py')) return 'Python'
  if (extensions.includes('ts') || extensions.includes('tsx')) return 'TypeScript'
  if (extensions.includes('js') || extensions.includes('jsx')) return 'JavaScript'
  if (extensions.includes('go')) return 'Go'
  if (extensions.includes('rs')) return 'Rust'
  return 'Pending detection'
}

function InvestigationWorkflow({ investigation, onSelect }: { investigation: Investigation; onSelect: (tab: Tab) => void }) {
  const { results } = investigation
  const executionStatus = results.execution_results.length ? results.execution_results.at(-1)?.status || 'recorded' : 'not-run'
  const verificationStatus = results.verification.status || 'not-run'
  const stages: Array<{ label: string; detail: string; status: string; tab?: Tab }> = [
    { label: 'Facts', detail: `${results.facts.length} observed`, status: results.facts.length ? 'recorded' : 'empty' },
    { label: 'Findings', detail: `${results.findings.length} linked`, status: results.findings.length ? 'recorded' : 'empty' },
    { label: 'Hypotheses', detail: `${results.hypotheses.length} ranked`, status: results.hypotheses.length ? 'ranked' : 'empty' },
    { label: 'Tests', detail: `${results.generated_tests.length} generated`, status: results.generated_tests.length ? 'ready' : 'empty', tab: 'tests' },
    { label: 'Execution', detail: results.execution_results.length ? `${results.execution_results.length} receipt${results.execution_results.length === 1 ? '' : 's'}` : 'not run', status: executionStatus, tab: 'tests' },
    { label: 'Verification', detail: verificationStatus === 'not-run' ? 'not checked' : verificationStatus.replace(/-/g, ' '), status: verificationStatus, tab: 'verification' },
  ]
  return <section className="workflow-panel" aria-label="Investigation status workflow"><div className="workflow-panel-heading"><div><div className="panel-kicker">EVIDENCE WORKFLOW</div><h2>Keep each claim in its lane</h2></div><span className="confidence-note">Observed → tested → checked</span></div><div className="workflow-stages">{stages.map((stage) => <button type="button" className={`workflow-stage workflow-stage--${statusTone(stage.status)}`} key={stage.label} onClick={() => stage.tab && onSelect(stage.tab)} disabled={!stage.tab} aria-label={`${stage.label}: ${stage.detail}`}><span className="workflow-stage-index" /> <span><strong>{stage.label}</strong><small>{stage.detail}</small></span></button>)}</div></section>
}

function statusTone(value: string): string {
  const normalized = value.toLowerCase()
  if (normalized.includes('pass') || normalized.includes('verified') || normalized === 'recorded' || normalized === 'ranked') return 'success'
  if (normalized.includes('run') || normalized.includes('pending') || normalized === 'ready' || normalized === 'not-run') return 'warning'
  if (normalized.includes('fail') || normalized.includes('error')) return 'danger'
  return 'neutral'
}

function Overview({ investigation, onRunTests, running, onOpenSource }: { investigation: Investigation; onRunTests: () => void; running: boolean; onOpenSource: () => void }) {
  const { results } = investigation
  const intakeLabels: Record<string, string> = { bug_description: 'Reporter description', reproduction_steps: 'Reproduction steps', expected_behavior: 'Expected behavior', actual_behavior: 'Actual behavior', environment: 'Environment' }
  const intakeEntries = Object.entries(investigation.source.intake || {})
  return <div className="diagnostic-grid"><div className="diagnostic-main">{intakeEntries.length > 0 && <section className="workspace-panel intake-panel"><div className="panel-kicker">REPORTER CONTEXT</div><div className="intake-grid">{intakeEntries.map(([key, value]) => <div key={key}><strong>{intakeLabels[key] || key.replace(/_/g, ' ')}</strong><p>{value}</p></div>)}</div></section>}<section className="workspace-panel finding-panel"><div className="panel-heading"><div><span className="panel-kicker">PROBABLE CAUSES</span><h2>What the evidence suggests</h2></div><span className="confidence-note">Ranked, not confirmed</span></div>{results.hypotheses.length ? <div className="hypothesis-list">{results.hypotheses.slice(0, 4).map((hypothesis, index) => <div className="hypothesis" key={`${hypothesis.text}-${index}`}><div className="hypothesis-rank">{String(index + 1).padStart(2, '0')}</div><div className="hypothesis-copy"><div className="hypothesis-title"><strong>{hypothesis.text}</strong><span>{Math.round(hypothesis.score * 100)}%</span></div><div className="confidence-bar"><span style={{ width: `${hypothesis.score * 100}%` }} /></div><p>{hypothesis.rationale}</p>{hypothesis.evidence.length > 0 && <EvidenceLine evidence={hypothesis.evidence[0]} />}</div></div>)}</div> : <EmptyState title="No hypotheses yet" description="The engine did not generate a ranked hypothesis for this input." />}</section><section className="workspace-panel findings-summary"><div className="panel-heading"><div><span className="panel-kicker">STATIC ANALYSIS</span><h2>Findings with evidence</h2></div><button className="text-link-button" onClick={onOpenSource}>View source ↗</button></div><div className="finding-list">{results.findings.slice(0, 4).map((finding, index) => <FindingRow finding={finding} key={`${finding.rule_id}-${index}`} />)}</div></section></div><aside className="diagnostic-side"><section className="workspace-panel fact-panel"><div className="panel-kicker">OBSERVED FACTS</div><h3>What Code-Aid knows</h3><div className="fact-list">{results.facts.map((fact, index) => <div className="fact" key={`${fact.text}-${index}`}><span className="fact-marker">✓</span><p>{fact.text}</p></div>)}</div></section><section className="workspace-panel test-cta"><div className="panel-kicker">NEXT CONTROLLED STEP</div><h3>Run the generated test.</h3><p>Execution is Docker-only, network-disabled, and bounded. A missing Docker runtime stays an explicit result.</p><button className="button button--primary button--full" onClick={onRunTests} disabled={running}>{running ? <><span className="button-spinner" /> Running safely…</> : <>Run generated tests <span>→</span></>}</button><div className="test-cta-foot">{results.generated_tests.length} test template ready</div></section></aside></div>
}

function SourceEvidence({ investigation }: { investigation: Investigation }) {
  const findings = investigation.results.findings
  const diagnostics = investigation.results.language_diagnostics || investigation.results.diagnostics || []
  return <div className="source-layout">
    <section className="workspace-panel traceback-panel">
      <div className="panel-heading"><div><span className="panel-kicker">RAW INPUT</span><h2>Traceback or error log</h2></div><span className="source-type-label">{String(investigation.source.metadata.exception_type || detectedLanguage(investigation))}</span></div>
      <pre className="traceback-viewer">{investigation.source.traceback}</pre>
      <div className="file-inventory"><div className="panel-kicker">PROJECT INVENTORY</div>{investigation.source.files.map((file) => <div className="file-row" key={file.path}><span className={`file-icon file-icon--${file.kind === 'python' ? 'py' : 'plain'}`}>{file.kind === 'python' ? 'py' : '·'}</span><code>{file.path}</code><small>{file.kind} · {file.size} B</small></div>)}</div>
    </section>
    <section className="workspace-panel source-findings">
      <div className="panel-heading"><div><span className="panel-kicker">LINKED EVIDENCE</span><h2>Source findings</h2></div></div>
      {findings.length ? <div className="finding-list">{findings.map((finding, index) => <FindingRow finding={finding} key={`${finding.rule_id}-${index}`} expanded />)}</div> : <EmptyState title="No static matches" description="No deterministic rule matched this traceback and source." />}
      <div className="language-diagnostics">
        <div className="panel-kicker">NATIVE TOOL DIAGNOSTICS</div>
        {diagnostics.length ? diagnostics.map((diagnostic, index) => <div className="language-diagnostic" key={`${diagnostic.path}-${diagnostic.line}-${index}`}><div><strong>{diagnostic.path}{diagnostic.line ? `:${diagnostic.line}${diagnostic.column ? `:${diagnostic.column}` : ''}` : ''}</strong><StatusPill value={diagnostic.severity} /></div><p>{diagnostic.message}</p><small>{diagnostic.tool}{diagnostic.code ? ` · ${diagnostic.code}` : ''}</small></div>) : <p className="diagnostics-empty">No compiler or parser diagnostics were emitted for the detected source files.</p>}
      </div>
    </section>
  </div>
}

function TestsPanel({ investigation, onRunTests, running }: { investigation: Investigation; onRunTests: () => void; running: boolean }) { const { generated_tests: tests, execution_results: executions } = investigation.results; return <div className="tests-layout"><section className="workspace-panel generated-tests-panel"><div className="panel-heading"><div><span className="panel-kicker">GENERATED, NOT YET PROOF</span><h2>Reproduction cases</h2></div><button className="button button--primary" onClick={onRunTests} disabled={running}>{running ? 'Running…' : 'Run in isolation →'}</button></div>{tests.map((test) => <div className="generated-test" key={test.path}><div className="generated-test-heading"><div><strong>{test.path}</strong><span>{test.purpose}</span></div><StatusPill value={test.validation_status} /></div><CodeBlock code={test.content} maxHeight={440} /></div>)}</section><aside className="workspace-panel execution-panel"><div className="panel-kicker">EXECUTION RECEIPTS</div><h3>What actually ran</h3>{executions.length === 0 ? <div className="execution-empty"><span>◷</span><p>Tests have not run yet.</p><small>Request an isolated run to add a receipt here.</small></div> : <div className="execution-list">{executions.slice().reverse().map((execution, index) => <div className="execution-receipt" key={`${execution.started_at}-${index}`}><div><StatusPill value={execution.status} /><span>{execution.duration_ms ? `${execution.duration_ms}ms` : '—'}</span></div><p>{execution.reason || (execution.status === 'passed' ? 'Generated test process exited successfully.' : 'The generated test process returned a failure.')}</p>{execution.stdout && <pre>{execution.stdout}</pre>}{execution.stderr && <pre>{execution.stderr}</pre>}</div>)}</div>}</aside></div> }

function VerificationPanel({ investigation, patchPath, setPatchPath, patchContent, setPatchContent, onSubmit, verifying, verification }: { investigation: Investigation; patchPath: string; setPatchPath: (value: string) => void; patchContent: string; setPatchContent: (value: string) => void; onSubmit: (event: FormEvent) => void; verifying: boolean; verification: VerificationResult }) { const suggestedFile = investigation.results.findings.flatMap((item) => item.evidence).find((item) => item.file)?.file || ''; const executionUnavailable = verification.status === 'execution-unavailable'; return <div className="verification-layout"><section className="workspace-panel patch-editor-panel"><div className="panel-heading"><div><span className="panel-kicker">NON-MUTATING CHECK</span><h2>Propose a source change</h2></div><span className="confidence-note">Original files stay untouched</span></div><form onSubmit={onSubmit}><label className="field"><span className="field-label">Relative file path</span><input value={patchPath} onChange={(event) => setPatchPath(event.target.value)} placeholder={suggestedFile || 'calculator.py'} /></label><label className="field"><span className="field-label">Proposed file content</span><textarea className="patch-textarea" value={patchContent} onChange={(event) => setPatchContent(event.target.value)} placeholder="Paste the complete proposed file. Code-Aid will parse it, show a diff, and—when Docker is available—run baseline and patched tests." rows={18} /></label><button className="button button--primary" disabled={verifying || !patchPath || !patchContent}>{verifying ? <><span className="button-spinner" /> Checking safely…</> : <>Verify proposed change <span>→</span></>}</button></form></section><aside className="workspace-panel verification-receipt"><div className="panel-kicker">VERIFICATION RECEIPT</div><h3>{verification.status === 'not-run' ? 'No patch checked.' : verification.status === 'verified' ? 'Behavior supported by tests.' : executionUnavailable ? 'Static check complete.' : 'Review the result.'}</h3><StatusPill value={verification.status} /><p>{verification.message || 'A syntax check, bounded path check, diff, and isolated baseline/patch comparison appear here after submission.'}</p>{verification.status !== 'not-run' && <div className="verification-metrics"><span><strong>{verification.original_failure_reproduced === true ? 'yes' : verification.original_failure_reproduced === false ? 'no' : '—'}</strong> original reproduced</span><span><strong>{verification.failure_disappeared === true ? 'yes' : verification.failure_disappeared === false ? 'no' : '—'}</strong> failure disappeared</span><span><strong>{verification.regressions_detected === true ? 'yes' : verification.regressions_detected === false ? 'no' : '—'}</strong> regressions detected</span></div>}{verification.baseline_execution && <ExecutionMini label="baseline" execution={verification.baseline_execution} />}{verification.patched_execution && <ExecutionMini label="proposed" execution={verification.patched_execution} />}{verification.checks?.map((check) => <div className="verification-check" key={check.name}><span className={check.status === 'passed' ? 'check-ok' : 'check-warn'}>{check.status === 'passed' ? '✓' : '!'}</span><div><strong>{check.name}</strong><small>{check.message}</small></div></div>)}</aside></div> }

function ExecutionMini({ label, execution }: { label: string; execution: { status: string; duration_ms: number | null; reason: string } }) { return <div className="execution-mini"><div><span>{label}</span><StatusPill value={execution.status} /></div><small>{execution.duration_ms ? `${execution.duration_ms}ms` : execution.reason || 'No receipt'}</small></div> }

function FindingRow({ finding, expanded = false }: { finding: Finding; expanded?: boolean }) { const evidence = finding.evidence[0]; return <div className={`finding-row severity-${finding.severity}`}><div className="finding-severity">{finding.severity === 'high' ? '!' : finding.severity === 'medium' ? '·' : 'i'}</div><div className="finding-copy"><div className="finding-title"><strong>{finding.rule_id.replace(/-/g, ' ')}</strong><span>{finding.severity}</span></div><p>{finding.text}</p>{evidence && <EvidenceLine evidence={evidence} expanded={expanded} />}</div></div> }
function EvidenceLine({ evidence, expanded = false }: { evidence: Evidence; expanded?: boolean }) { return <div className="evidence-line"><span>↳</span><code>{evidence.file || 'traceback'}{evidence.line ? `:${evidence.line}` : ''}</code><span>{evidence.reason}</span>{expanded && evidence.snippet && <pre>{evidence.snippet}</pre>}</div> }
