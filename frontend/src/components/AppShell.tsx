import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'

function Mark() {
  return (
    <span className="brand-mark" aria-hidden="true">
      <span />
      <span />
      <span />
    </span>
  )
}

export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <Link className={`brand ${compact ? 'brand--compact' : ''}`} to="/">
      <Mark />
      <span>code<span className="brand-accent">-aid</span></span>
    </Link>
  )
}

export function AppShell() {
  const location = useLocation()
  const inWorkspace = location.pathname.startsWith('/app')
  return (
    <div className="app-frame">
      <aside className="app-sidebar">
        <div className="sidebar-top">
          <Brand compact />
          <span className="sidebar-build">LOCAL BUILD / 0.1</span>
        </div>
        <nav className="sidebar-nav" aria-label="Workspace navigation">
          <span className="nav-group-label">Workspace</span>
          <NavLink className={({ isActive }) => `sidebar-link ${isActive && location.pathname === '/app' ? 'active' : ''}`} to="/app" end>
            <span className="nav-icon">⌂</span><span>Overview</span>
          </NavLink>
          <NavLink className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`} to="/app/new">
            <span className="nav-icon">＋</span><span>New investigation</span>
          </NavLink>
          <span className="nav-group-label nav-group-label--spaced">System</span>
          <NavLink className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`} to="/docs">
            <span className="nav-icon">?</span><span>Documentation</span>
          </NavLink>
          <NavLink className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`} to="/app/settings">
            <span className="nav-icon">⚙</span><span>Settings</span>
          </NavLink>
        </nav>
        <div className="sidebar-bottom">
          <div className="runtime-card">
            <div className="runtime-dot" />
            <div>
              <strong>Local runtime</strong>
              <span>Data stays on this machine</span>
            </div>
          </div>
          <a className="sidebar-footer-link" href="#open-source">Source &amp; security ↗</a>
        </div>
      </aside>
      <div className="app-main">
        <header className="workspace-header">
          <div className="mobile-brand"><Brand compact /></div>
          <div className="breadcrumbs" aria-label="Breadcrumb">
            <span>Code-Aid</span><span className="crumb-separator">/</span><strong>{inWorkspace ? 'Workspace' : 'Documentation'}</strong>
          </div>
          <div className="header-actions">
            <span className="header-status"><span className="status-dot" /> engine ready</span>
            <Link className="header-new-button" to="/app/new"><span>＋</span> New investigation</Link>
          </div>
        </header>
        <main className="workspace-content"><Outlet /></main>
      </div>
    </div>
  )
}

export function PageIntro({ eyebrow, title, description, action }: { eyebrow?: string; title: string; description?: string; action?: React.ReactNode }) {
  return (
    <div className="page-intro">
      <div>
        {eyebrow && <div className="eyebrow eyebrow--small"><span className="eyebrow-line" />{eyebrow}</div>}
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {action && <div className="page-intro-action">{action}</div>}
    </div>
  )
}

export function StatusPill({ value }: { value: string }) {
  const normalized = value.toLowerCase()
  const tone = normalized.includes('pass') || normalized === 'analyzed' || normalized === 'verified' ? 'success' : normalized.includes('fail') || normalized === 'error' ? 'danger' : normalized.includes('run') || normalized === 'pending' ? 'warning' : 'neutral'
  return <span className={`status-pill status-pill--${tone}`}><span className="status-pill-dot" />{value.replace(/-/g, ' ')}</span>
}

export function CodeBlock({ code, language = 'python', maxHeight = 360 }: { code: string; language?: string; maxHeight?: number }) {
  const lines = code.split('\n')
  return (
    <div className="code-block" style={{ maxHeight }}>
      <div className="code-toolbar"><span>{language}</span><span>{lines.length} lines</span></div>
      <pre><code>{lines.map((line, index) => <span className="code-line" key={`${index}-${line}`}><span className="line-number">{String(index + 1).padStart(2, '0')}</span><span className="line-content">{line || ' '}</span></span>)}</code></pre>
    </div>
  )
}

export function EmptyState({ title, description, action }: { title: string; description: string; action?: React.ReactNode }) {
  return <div className="empty-state"><div className="empty-glyph">∅</div><h3>{title}</h3><p>{description}</p>{action}</div>
}

export function ErrorNotice({ message, onDismiss }: { message: string; onDismiss?: () => void }) {
  return <div className="notice notice--error" role="alert"><span className="notice-icon">!</span><span>{message}</span>{onDismiss && <button className="icon-button notice-close" onClick={onDismiss} aria-label="Dismiss error">×</button>}</div>
}
