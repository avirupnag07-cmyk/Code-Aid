import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Brand, PageIntro } from '../components/AppShell'

const sections = [
  ['overview', 'Overview'],
  ['quick-start', 'Quick start'],
  ['architecture', 'Architecture'],
  ['pipeline', 'Analysis pipeline'],
  ['security', 'Security model'],
  ['limitations', 'Limitations'],
]

export function DocsPage() {
  const [active, setActive] = useState('overview')

  return (
    <div className="docs-shell">
      <header className="docs-header">
        <Brand />
        <nav><Link to="/app">Open workspace ↗</Link></nav>
      </header>
      <div className="docs-layout">
        <aside className="docs-nav">
          <div className="docs-nav-title">CODE-AID / DOCS</div>
          {sections.map(([id, label]) => (
            <a className={active === id ? 'active' : ''} href={`#${id}`} key={id} onClick={() => setActive(id)}>{label}</a>
          ))}
          <div className="docs-nav-footer"><span>VERSION</span><strong>0.1.0 · local build</strong></div>
        </aside>
        <main className="docs-content">
          <PageIntro eyebrow="FIELD NOTES" title="Documentation" description="How Code-Aid turns an error report into a bounded, evidence-backed investigation." />

          <DocSection id="overview" title="A diagnostic workspace, not a chatbot">
             <p>Code-Aid is a local-first Bug Reproduction Engineer. It detects supported source languages, runs native syntax or compiler checks when the toolchain is present, and preserves the difference between what was observed, what static analysis found, what the engine thinks might be happening, and what a test actually proved.</p>
            <div className="docs-callout"><strong>Core promise</strong><span>Analysis is useful without an external model. Execution is never silently moved into the API process.</span></div>
          </DocSection>

          <DocSection id="quick-start" title="Quick start">
            <p>Run the backend and frontend in two terminals from a clean checkout.</p>
            <pre className="docs-code">{`# terminal 1 — API
cd backend
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m uvicorn app.main:app --reload --port 8000

# terminal 2 — interface
cd frontend
npm ci
npm run dev`}</pre>
            <p>Open <code>http://localhost:5173</code>. Select “Checkout tax calculator” from the sample picker, then analyze. The API is also documented at <code>http://localhost:8000/docs</code>.</p>
          </DocSection>

          <DocSection id="architecture" title="Architecture">
             <p>The repository uses a deliberately small split between a FastAPI service and a Vite-built React interface. Language adapters sit behind a shared registry so toolchain availability is reported instead of guessed.</p>
            <div className="architecture-diagram">
              <div><span>React / Vite</span><small>forms · workspace · reports</small></div><b>↕ JSON / multipart</b>
              <div><span>FastAPI</span><small>validation · routes · CORS</small></div><b>↕</b>
              <div><span>Engine modules</span><small>ingest · parse · AST · rank · generate</small></div><b>↕</b>
              <div><span>SQLite + project store</span><small>durable records · private source copy</small></div>
            </div>
            <p>The engine modules expose plain Python boundaries so other languages can be added later without rewriting persistence or the user interface.</p>
          </DocSection>

          <DocSection id="pipeline" title="Analysis pipeline">
            <ol className="docs-steps">
              <li><strong>Ingestion.</strong> ZIP members are checked for absolute names, traversal, symlinks, member count, and byte budgets. Source is copied as data; no project module is imported.</li>
              <li><strong>Traceback parsing.</strong> Common Python exception families and frames are extracted from complete or pytest-prefixed traces. Malformed input returns a validation error.</li>
               <li><strong>Static analysis.</strong> Python AST parsing matches deterministic rules, including unresolved names, local function argument mismatches, unsafe mapping lookup, attribute access, numeric conversion, mixed literal operations, inconsistent returns, and broad exception handling. Other adapters normalize native compiler/parser diagnostics.</li>
              <li><strong>Hypotheses.</strong> Findings and the exception family are ranked with stable rules. A score is a confidence signal, not a diagnosis.</li>
               <li><strong>Test generation.</strong> Bundled Python metadata can provide a module, function, args, and expected output. The generated pytest source is parsed and structurally checked. Non-Python projects are not given a misleading Python test; their matrix entry says when generation is not configured.</li>
              <li><strong>Execution.</strong> Only Docker is eligible. The runner uses no network, no privileged flag, bounded CPU/memory/PIDs, read-only project mounts, and a timeout. Missing Docker returns <code>unavailable</code>.</li>
              <li><strong>Verification.</strong> Proposed complete file contents are checked for safe relative paths, size, Python syntax, and a unified diff. When Docker is available, baseline and staged-patch test runs are compared without mutating the stored project.</li>
            </ol>
          </DocSection>

          <DocSection id="security" title="Security model">
            <p>Code-Aid treats every uploaded archive as untrusted. The API process performs inspection and AST parsing, not execution. Generated tests are written to a temporary directory and mounted read-only into the isolated runner.</p>
            <div className="security-grid">
              <div><strong>Implemented</strong><span>Path traversal rejection</span><span>Symlink rejection</span><span>Archive and output limits</span><span>Network-disabled container request</span><span>Non-mutating patch verification</span></div>
              <div><strong>Operator responsibilities</strong><span>Keep Docker patched and isolated</span><span>Do not expose the local API publicly</span><span>Review uploaded source before execution</span><span>Understand container-runtime policy</span></div>
            </div>
            <p>Container isolation is a defense-in-depth boundary, not a guarantee of perfect security. The local runner depends on the Docker daemon and its host policy.</p>
          </DocSection>

          <DocSection id="limitations" title="Known limitations">
             <ul className="docs-list">
               <li>Analysis adapters cover Python, JavaScript, TypeScript, Java, C, C++, Go, and Rust. Native analysis is marked unavailable when the required compiler or parser is not installed.</li>
               <li>Python is the only language with the current deterministic AST rule set and pytest generation flow.</li>
              <li>Generated tests need enough sample metadata to call a known function. Otherwise they are clearly marked as skipped templates.</li>
              <li>Docker is not bundled with the application. Without a daemon, tests cannot execute and the UI records that fact.</li>
              <li>Patch verification is limited to the generated tests; it does not run a full project suite or guarantee that untested regressions are absent.</li>
              <li>There is no authentication. This is intentional for the local-first MVP; do not expose the development server to an untrusted network.</li>
              <li>The deterministic AST rules are intentionally narrow and do not detect every possible bug.</li>
            </ul>
          </DocSection>

          <section className="docs-next"><Link className="button button--primary" to="/app/new">Create an investigation <span>↗</span></Link><Link className="text-link" to="/app">Return to workspace</Link></section>
        </main>
      </div>
      <footer className="docs-footer"><Brand compact /><span>Code-Aid · local-first developer tooling</span></footer>
    </div>
  )
}

function DocSection({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return <section className="doc-section" id={id}><div className="doc-section-marker">#</div><div><h2>{title}</h2>{children}</div></section>
}
