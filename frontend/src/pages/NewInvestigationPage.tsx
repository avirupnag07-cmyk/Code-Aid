import { ChangeEvent, FormEvent, useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { ErrorNotice, PageIntro } from '../components/AppShell'
import { api } from '../lib/api'
import type { CreateInvestigationInput, GitHubRepository, GitHubStatus, Sample } from '../lib/types'

const emptyForm: CreateInvestigationInput = { title: '', bugDescription: '', traceback: '', sampleId: '', reproductionSteps: '', expectedBehavior: '', actualBehavior: '', environment: '', archive: null, repositoryUrl: '', repositoryRef: 'main', repositorySubdirectory: '' }
type SourceMode = 'sample' | 'zip' | 'git'

export function NewInvestigationPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [samples, setSamples] = useState<Sample[]>([])
  const [form, setForm] = useState<CreateInvestigationInput>(emptyForm)
  const [loadingSamples, setLoadingSamples] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [fieldError, setFieldError] = useState('')
  const [sourceMode, setSourceMode] = useState<SourceMode>('sample')
  const [github, setGithub] = useState<GitHubStatus | null>(null)
  const [githubRepositories, setGithubRepositories] = useState<GitHubRepository[]>([])

  useEffect(() => {
    api.samples().then((items) => {
      setSamples(items)
      const requested = searchParams.get('sample')
      if (requested && items.some((item) => item.id === requested)) setForm((current) => ({ ...current, sampleId: requested }))
    }).catch((cause: Error) => setError(cause.message)).finally(() => setLoadingSamples(false))
    api.githubStatus().then(setGithub).catch(() => setGithub(null))
  }, [searchParams])

  useEffect(() => {
    if (!github?.connected) return
    api.githubRepositories().then(setGithubRepositories).catch((cause: Error) => setError(cause.message))
  }, [github?.connected])

  function update<K extends keyof CreateInvestigationInput>(key: K, value: CreateInvestigationInput[K]) { setForm((current) => ({ ...current, [key]: value })) }
  function chooseSample(sampleId: string) { setSourceMode('sample'); setForm((current) => ({ ...current, sampleId, archive: null, repositoryUrl: '' })) }
  function onArchive(event: ChangeEvent<HTMLInputElement>) { const file = event.target.files?.[0] || null; setSourceMode('zip'); setForm((current) => ({ ...current, archive: file, sampleId: '', repositoryUrl: '' })) }
  function chooseGit() { setSourceMode('git'); setForm((current) => ({ ...current, sampleId: '', archive: null })) }
  function chooseGithubRepository(item: GitHubRepository) { setSourceMode('git'); setForm((current) => ({ ...current, sampleId: '', archive: null, repositoryUrl: item.clone_url, repositoryRef: item.default_branch || 'main' })) }
  async function submit(event: FormEvent) {
    event.preventDefault(); setFieldError(''); setError('')
    if (!form.title.trim()) return setFieldError('Give this investigation a short, descriptive title.')
    if (sourceMode === 'sample' && !form.sampleId) return setFieldError('Choose a bundled sample.')
    if (sourceMode === 'zip' && !form.archive) return setFieldError('Choose a ZIP archive.')
    if (sourceMode === 'git' && (!form.repositoryUrl?.trim() || !form.repositoryRef?.trim())) return setFieldError('Enter a repository URL and revision.')
    setSubmitting(true)
    try { const result = await api.createInvestigation(form); navigate(`/app/investigations/${result.id}`) } catch (cause) { setError(cause instanceof Error ? cause.message : 'The investigation could not be created.') } finally { setSubmitting(false) }
  }

  return <>
     <PageIntro eyebrow="NEW INVESTIGATION" title="Put the failure on the bench." description="Start with the smallest useful set of facts. Code-Aid detects the project language during source inspection and keeps observations, hypotheses, generated tests, and verification separate." />
    {error && <ErrorNotice message={error} onDismiss={() => setError('')} />}
    <form className="investigation-form" onSubmit={submit}>
      <div className="form-main">
        <section className="form-section"><div className="form-section-heading"><span className="form-index">01</span><div><h2>Describe the failure</h2><p>These notes travel with the investigation report.</p></div></div><Field label="Investigation title" hint="Required"><input value={form.title} onChange={(event) => update('title', event.target.value)} placeholder="e.g. Checkout tax calculation rejects numeric rates" maxLength={120} /></Field><Field label="What went wrong?" hint="Optional"><textarea value={form.bugDescription} onChange={(event) => update('bugDescription', event.target.value)} placeholder="Describe the observed behavior in plain language." rows={4} /></Field><div className="two-fields"><Field label="Expected behavior"><textarea value={form.expectedBehavior} onChange={(event) => update('expectedBehavior', event.target.value)} placeholder="What should happen?" rows={3} /></Field><Field label="Actual behavior"><textarea value={form.actualBehavior} onChange={(event) => update('actualBehavior', event.target.value)} placeholder="What happened instead?" rows={3} /></Field></div></section>
         <section className="form-section"><div className="form-section-heading"><span className="form-index">02</span><div><h2>Bring the error</h2><p>Paste the error exactly as reported; language is detected from the source.</p></div></div><Field label="Traceback or error log" hint="Required for analysis"><textarea className="traceback-input" value={form.traceback} onChange={(event) => update('traceback', event.target.value)} placeholder={'Traceback or error log\n  File "src/calculator.py", line 5\n    return amount + tax\nTypeError: unsupported operand type(s)...'} rows={10} /></Field></section>
        <section className="form-section"><div className="form-section-heading"><span className="form-index">03</span><div><h2>Add context <span className="optional-label">optional</span></h2><p>Reproduction steps and environment help the next reader.</p></div></div><Field label="Reproduction steps"><textarea value={form.reproductionSteps} onChange={(event) => update('reproductionSteps', event.target.value)} placeholder={'1. Call add_tax(100.0, "8")\n2. Observe the exception'} rows={4} /></Field><Field label="Environment"><textarea value={form.environment} onChange={(event) => update('environment', event.target.value)} placeholder="Python version, OS, dependency versions, or CI context." rows={3} /></Field></section>
     </div>
        <aside className="form-aside">
          <div className="source-picker">
            <div className="form-aside-title"><span className="form-index">04</span><div><h2>Choose a project</h2><p>Import a sample, ZIP, or read-only Git revision.</p></div></div>
            <div className="source-mode-tabs" role="tablist" aria-label="Project import method">
              <button type="button" className={sourceMode === 'sample' ? 'active' : ''} onClick={() => setSourceMode('sample')}>Sample</button>
              <button type="button" className={sourceMode === 'zip' ? 'active' : ''} onClick={() => setSourceMode('zip')}>ZIP upload</button>
              <button type="button" className={sourceMode === 'git' ? 'active' : ''} onClick={chooseGit}>Public Git</button>
            </div>
            {sourceMode === 'sample' && (loadingSamples ? <div className="source-loading">Loading bundled samples…</div> : <div className="sample-options">{samples.map((sample) => <button type="button" className={`sample-option ${form.sampleId === sample.id ? 'selected' : ''}`} key={sample.id} onClick={() => chooseSample(sample.id)}><span className="sample-radio">{form.sampleId === sample.id ? '●' : '○'}</span><span><strong>{sample.name}</strong><small>{sample.exception_type} · {sample.file_count} files</small></span></button>)}</div>)}
            {sourceMode === 'zip' && <label className={`upload-dropzone ${form.archive ? 'has-file' : ''}`}><input type="file" accept=".zip,application/zip" onChange={onArchive} /><span className="upload-symbol">{form.archive ? '✓' : '⇧'}</span><strong>{form.archive ? form.archive.name : 'Upload a project ZIP'}</strong><small>{form.archive ? `${Math.ceil(form.archive.size / 1024)} KB selected` : '10 MB limit · language detected during inspection'}</small></label>}
            {sourceMode === 'git' && <div className="git-source-fields"><Field label="HTTPS repository URL"><input value={form.repositoryUrl || ''} onChange={(event) => update('repositoryUrl', event.target.value)} placeholder="https://github.com/org/project.git" /></Field><Field label="Branch, tag, or commit"><input value={form.repositoryRef || ''} onChange={(event) => update('repositoryRef', event.target.value)} placeholder="main or 40-character SHA" /></Field><Field label="Optional subdirectory"><input value={form.repositorySubdirectory || ''} onChange={(event) => update('repositorySubdirectory', event.target.value)} placeholder="packages/service" /></Field><p className="source-help">Only allowlisted public HTTPS hosts are accepted. The selected ref is resolved to an exact commit SHA before analysis; submodules and project scripts are not initialized.</p></div>}
            {github && <div className="github-source-card"><div><strong>GitHub private repositories</strong><small>{github.connected ? 'Connected · read-only import available' : github.configured ? 'Connect to list repositories you can access' : 'OAuth is not configured on this server'}</small></div>{github.connected ? <><select aria-label="GitHub repository" defaultValue="" onChange={(event) => { const item = githubRepositories.find((repo) => repo.full_name === event.target.value); if (item) chooseGithubRepository(item) }}><option value="">Select a connected repository</option>{githubRepositories.map((repo) => <option value={repo.full_name} key={repo.id}>{repo.full_name}{repo.private ? ' · private' : ''}</option>)}</select><button type="button" className="text-link-button" onClick={() => api.githubDisconnect().then(setGithub)}>Disconnect GitHub</button></> : github.configured ? <a className="text-link" href={api.githubAuthorizeUrl()}>Connect GitHub ↗</a> : <small>Set GitHub OAuth variables to enable private imports.</small>}</div>}
            <div className="security-note"><span>⌁</span><p>Repositories are copied to a temporary restricted workspace. Credentials never enter repository metadata or reports.</p></div>
          </div>
          <div className="submit-card">{fieldError && <p className="field-error" role="alert">{fieldError}</p>}<button className="button button--primary button--full" type="submit" disabled={submitting}>{submitting ? <><span className="button-spinner" /> Importing and analyzing…</> : <>Analyze investigation <span>↗</span></>}</button><Link className="cancel-link" to="/app">Cancel and return to desk</Link></div>
        </aside>
    </form>
  </>
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) { return <label className="field"><span className="field-label">{label}{hint && <small>{hint}</small>}</span>{children}</label> }
