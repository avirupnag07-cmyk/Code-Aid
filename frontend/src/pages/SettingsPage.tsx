import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ErrorNotice, PageIntro } from '../components/AppShell'
import { api } from '../lib/api'

export function SettingsPage() {
  const [health, setHealth] = useState<{ status: string; service: string; version: string; database: string } | null>(null)
  const [error, setError] = useState('')
  useEffect(() => { api.health().then(setHealth).catch((cause: Error) => setError(cause.message)) }, [])
  return <><PageIntro eyebrow="SYSTEM SETTINGS" title="Settings" description="Configuration for this local Code-Aid workspace." />{error && <ErrorNotice message={error} />}<div className="settings-grid"><section className="workspace-panel settings-panel"><div className="panel-kicker">RUNTIME</div><h2>Local service</h2><p>The workspace connects to the FastAPI service through the configured Vite proxy. Records are stored in SQLite under the backend data directory.</p><div className="settings-row"><span>API status</span><strong className={health?.status === 'ok' ? 'text-success' : ''}>{health ? health.status : 'checking…'}</strong></div><div className="settings-row"><span>Service</span><strong>{health?.service || '—'}</strong></div><div className="settings-row"><span>Version</span><strong>{health?.version || '—'}</strong></div><div className="settings-row"><span>Database</span><strong>{health?.database || '—'}</strong></div></section><section className="workspace-panel settings-panel"><div className="panel-kicker">BOUNDARIES</div><h2>Execution policy</h2><p>Code-Aid will not fall back to running uploaded project code in the API process. Configure Docker separately when you need test execution.</p><div className="toggle-row"><span><strong>Network access</strong><small>Disabled for the runner</small></span><span className="toggle toggle--off">OFF</span></div><div className="toggle-row"><span><strong>Host mounts</strong><small>Not provided to test containers</small></span><span className="toggle toggle--off">OFF</span></div><Link className="text-link" to="/docs#security">Read the security model ↗</Link></section></div></>
}
