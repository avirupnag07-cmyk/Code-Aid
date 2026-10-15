import { Link } from 'react-router-dom'
import { Brand } from '../components/AppShell'

function Arrow() { return <span className="arrow-mark" aria-hidden="true">↗</span> }

function ProductPreview() {
  return (
    <div className="product-preview" aria-label="Code-Aid workspace preview">
      <div className="preview-topbar"><div className="window-dots"><i /><i /><i /></div><span>code-aid / workspace</span><span className="preview-state"><b /> idle</span></div>
      <div className="preview-body">
        <div className="preview-sidebar">
          <div className="preview-mini-brand"><span className="mini-mark">◆</span> investigations</div>
          <div className="preview-side-item preview-side-item--active"><span>◌</span> New investigation</div>
          <div className="preview-side-item"><span>□</span> Samples</div>
          <div className="preview-side-item"><span>⌘</span> Reports</div>
        </div>
        <div className="preview-main">
          <div className="preview-eyebrow">READY FOR INPUT</div>
          <h3>Start with the evidence you already have.</h3>
          <p>Paste a traceback or choose a bundled Python sample to create a real investigation.</p>
          <div className="preview-input-lines"><span>traceback</span><span>source archive</span><span>environment</span></div>
          <div className="preview-empty-line"><span className="pulse-dot" /> no investigation running</div>
        </div>
      </div>
      <div className="preview-footer"><span>facts / findings / hypotheses / verification</span><span>local-only by default</span></div>
    </div>
  )
}

export function LandingPage() {
  return (
    <div className="marketing-page">
      <header className="marketing-nav site-container">
        <Brand />
        <nav className="marketing-links" aria-label="Main navigation">
          <a href="#product">Product</a><a href="#features">Features</a><a href="#workflow">How it works</a><Link to="/docs">Documentation</Link><a href="#open-source">GitHub</a>
        </nav>
        <Link className="button button--outline button--nav" to="/app">Open workspace <Arrow /></Link>
      </header>

      <main>
        <section className="hero site-container" id="product">
          <div className="hero-copy">
            <div className="eyebrow"><span className="eyebrow-line" />BUGS EXPLAINED. TESTS GENERATED. FIXES VERIFIED.</div>
            <h1>From vague bug reports to <em>reproducible fixes.</em></h1>
            <p className="hero-lede">Code-Aid investigates errors, identifies likely causes, creates reproducible tests, and helps you verify fixes with evidence.</p>
            <div className="hero-actions"><Link className="button button--primary" to="/app/new">Start an investigation <Arrow /></Link><a className="button button--quiet" href="#workflow">Explore the workflow <span>↓</span></a></div>
            <p className="hero-note"><span className="status-dot" /> Local-first. Deterministic analysis. No model key required.</p>
          </div>
          <div className="hero-visual"><ProductPreview /><div className="visual-caption"><span>01</span><span>Empty states are honest by design.</span></div></div>
        </section>

        <section className="manifesto site-container section-rule">
          <div className="manifesto-kicker">THE PROBLEM WITH A STACK TRACE</div>
          <div className="manifesto-body"><h2>A traceback tells you <em>where</em> the program stopped. It rarely tells you what to test next.</h2><p>Code-Aid turns a bug report into a bounded investigation: the input is preserved, source evidence is linked, hypotheses stay provisional, and test results are recorded separately from suggestions.</p></div>
        </section>

        <section className="feature-section site-container" id="features">
          <div className="section-heading"><div><div className="eyebrow eyebrow--muted">BUILT FOR THE FIRST 30 MINUTES</div><h2>Less guessing. More evidence.</h2></div><p>The first release focuses on Python projects and keeps the core path useful without a paid AI service.</p></div>
          <div className="feature-grid">
            <Feature number="01" title="Ingest without executing" text="ZIP validation, path traversal checks, size limits, and a source inventory happen before any project code can run." code="ZIP → validate → inventory" />
            <Feature number="02" title="Read the failure in context" text="Traceback frames are resolved to source lines, then deterministic AST rules add evidence-backed findings." code="frame → AST → evidence" />
            <Feature number="03" title="Generate a focused test" text="Project metadata and the reported exception shape a pytest template. Generated code is parsed before it is eligible to run." code="input → pytest → validate" />
            <Feature number="04" title="Verify, don’t overclaim" text="Docker-only execution and non-mutating patch checks keep passing tests, hypotheses, and suggested fixes distinct." code="run → compare → report" />
          </div>
        </section>

        <section className="workflow-section" id="workflow">
          <div className="site-container"><div className="eyebrow eyebrow--muted">THE INVESTIGATION LOOP</div><h2>Four stages between “it broke” and “we know why.”</h2>
            <div className="workflow-grid"><WorkflowStep number="01" title="Capture" text="Describe the bug, paste the error, and select a sample or upload a Python ZIP." /><WorkflowStep number="02" title="Inspect" text="Resolve frames, inventory files, and surface static findings with line-level evidence." /><WorkflowStep number="03" title="Reproduce" text="Generate a test template, review it, then request isolated execution when Docker is available." /><WorkflowStep number="04" title="Verify" text="Compare a proposed file change and export a report that records exactly what was checked." /></div>
          </div>
        </section>

        <section className="terminal-section site-container">
          <div className="terminal-intro"><div className="eyebrow eyebrow--muted">THE COMMAND-LINE SHAPE</div><h2>Works as a workspace first. Leaves a useful trail behind.</h2><p>Every investigation can be exported as Markdown for a pull request, issue, or handoff. The terminal panel below describes the contract; it is not a fabricated run.</p></div>
          <div className="terminal"><div className="terminal-bar"><span className="terminal-dot terminal-dot--red" /><span className="terminal-dot terminal-dot--yellow" /><span className="terminal-dot terminal-dot--green" /><span className="terminal-title">code-aid / report</span></div><pre><code><span className="terminal-muted">$</span> <span className="terminal-command">open workspace</span>{'\n'}<span className="terminal-muted">›</span> <span className="terminal-label">source</span>      choose bundled sample or .zip{'\n'}<span className="terminal-muted">›</span> <span className="terminal-label">analysis</span>    parse traceback / inspect AST{'\n'}<span className="terminal-muted">›</span> <span className="terminal-label">evidence</span>    facts separated from hypotheses{'\n'}<span className="terminal-muted">›</span> <span className="terminal-label">execution</span>  Docker-only when available{'\n'}<span className="terminal-muted">›</span> <span className="terminal-label">report</span>     export Markdown</code></pre><div className="terminal-foot">No external model, network, or host execution is required for analysis.</div></div>
        </section>

        <section className="security-section site-container section-rule">
          <div className="security-icon">⌁</div><div><div className="eyebrow eyebrow--muted">SAFETY AS A PRODUCT FEATURE</div><h2>Untrusted code stays untrusted.</h2><p>Uploads are treated as bytes during ingestion. The runner never falls back to executing a project in the API process. When Docker is unavailable, Code-Aid reports that limitation instead of pretending to run a test.</p><div className="security-list"><span>Path traversal protection</span><span>Bounded archives</span><span>No network by default</span><span>Explicit unavailable state</span></div></div>
        </section>

        <section className="capabilities-section site-container">
          <div className="capabilities-heading"><div className="eyebrow eyebrow--muted">CURRENTLY SUPPORTED</div><h2>Small surface. Clear boundaries.</h2></div>
          <div className="capability-table"><Capability label="Language" value="Python 3 source projects" /><Capability label="Tracebacks" value="10 common exception families" /><Capability label="Static analysis" value="AST rules with evidence" /><Capability label="Test format" value="pytest templates" /><Capability label="Storage" value="local SQLite" /><Capability label="Export" value="Markdown diagnostic report" /></div>
        </section>

        <section className="open-source-section site-container" id="open-source"><div className="open-source-copy"><div className="eyebrow eyebrow--muted">OPEN BY DEFAULT</div><h2>A tool you can inspect, run, and extend locally.</h2><p>The local build is intentionally self-contained: no accounts, no paid service, and no production credentials. Read the architecture and security notes before enabling isolated execution for untrusted projects.</p><div className="hero-actions"><Link className="button button--outline" to="/docs">Read the documentation <Arrow /></Link><Link className="text-link" to="/app">Open the workspace <Arrow /></Link></div></div><div className="open-source-stamp"><span>CA</span><small>LOCAL /<br />OPEN BUILD</small></div></section>

        <section className="final-cta site-container"><div className="eyebrow">MAKE THE NEXT FAILURE REPRODUCIBLE</div><h2>Start with the evidence.<br /><em>End with a test.</em></h2><Link className="button button--primary" to="/app/new">Start an investigation <Arrow /></Link></section>
      </main>
      <footer className="marketing-footer site-container"><Brand compact /><div className="footer-note">Code-Aid · From bug reports to reproducible fixes.<br /><span>Local-first developer tooling. No unsupported claims.</span></div><div className="footer-links"><Link to="/docs">Documentation</Link><a href="#open-source">Source &amp; security</a><Link to="/app">Workspace</Link></div></footer>
    </div>
  )
}

function Feature({ number, title, text, code }: { number: string; title: string; text: string; code: string }) {
  return <article className="feature-item"><div className="feature-number">{number}</div><h3>{title}</h3><p>{text}</p><code>{code}</code></article>
}
function WorkflowStep({ number, title, text }: { number: string; title: string; text: string }) { return <article className="workflow-step"><span>{number}</span><h3>{title}</h3><p>{text}</p></article> }
function Capability({ label, value }: { label: string; value: string }) { return <div className="capability-row"><span>{label}</span><strong>{value}</strong><span className="capability-check">✓</span></div> }
