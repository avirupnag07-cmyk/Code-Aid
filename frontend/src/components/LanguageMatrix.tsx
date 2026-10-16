import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import type { LanguageSupport, LanguagesResponse } from '../lib/types'

const FALLBACK_LANGUAGES: LanguageSupport[] = [
  {
    id: 'python',
    name: 'Python',
    extensions: ['.py'],
    status: 'supported',
    detection: 'supported',
    syntax: 'supported',
    analysis: 'supported',
    diagnostics: 'supported',
    test_generation: 'pytest-template',
    execution: 'supported',
    notes: 'Traceback parsing, AST analysis, generated tests',
  },
  {
    id: 'javascript',
    name: 'JavaScript',
    extensions: ['.js', '.jsx', '.mjs', '.cjs'],
    status: 'supported', detection: 'supported', syntax: 'toolchain-dependent', analysis: 'toolchain-dependent', diagnostics: 'toolchain-dependent', test_generation: 'not-configured', execution: 'not-configured',
    notes: 'node --check when Node is installed',
  },
  {
    id: 'typescript',
    name: 'TypeScript',
    extensions: ['.ts', '.tsx'],
    status: 'supported', detection: 'supported', syntax: 'toolchain-dependent', analysis: 'toolchain-dependent', diagnostics: 'toolchain-dependent', test_generation: 'not-configured', execution: 'not-configured',
    notes: 'tsc --noEmit when TypeScript is installed',
  },
  {
    id: 'java', name: 'Java', extensions: ['.java'], status: 'supported', detection: 'supported', syntax: 'toolchain-dependent', analysis: 'toolchain-dependent', diagnostics: 'toolchain-dependent', test_generation: 'not-configured', execution: 'not-configured', notes: 'javac check mode when Java is installed',
  },
  {
    id: 'c', name: 'C', extensions: ['.c', '.h'], status: 'supported', detection: 'supported', syntax: 'toolchain-dependent', analysis: 'toolchain-dependent', diagnostics: 'toolchain-dependent', test_generation: 'not-configured', execution: 'not-configured', notes: 'gcc syntax-only mode when GCC is installed',
  },
  {
    id: 'cpp', name: 'C++', extensions: ['.cc', '.cpp', '.cxx', '.hpp'], status: 'supported', detection: 'supported', syntax: 'toolchain-dependent', analysis: 'toolchain-dependent', diagnostics: 'toolchain-dependent', test_generation: 'not-configured', execution: 'not-configured', notes: 'g++ syntax-only mode when a C++ compiler is installed',
  },
  {
    id: 'go',
    name: 'Go',
    extensions: ['.go'],
    status: 'supported', detection: 'supported', syntax: 'toolchain-dependent', analysis: 'toolchain-dependent', diagnostics: 'toolchain-dependent', test_generation: 'not-configured', execution: 'not-configured',
    notes: 'go tool compile when Go is installed',
  },
  {
    id: 'rust',
    name: 'Rust',
    extensions: ['.rs'],
    status: 'supported', detection: 'supported', syntax: 'toolchain-dependent', analysis: 'toolchain-dependent', diagnostics: 'toolchain-dependent', test_generation: 'not-configured', execution: 'not-configured',
    notes: 'rustc or Cargo check when Rust is installed',
  },
]

function text(value: unknown, fallback: string): string {
  return typeof value === 'string' && value.trim() ? value : fallback
}

function list(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value.filter((item): item is string => typeof item === 'string')
}

function normalizeLanguage(value: unknown, key?: string): LanguageSupport | null {
  if (!value || typeof value !== 'object') return null
  const item = value as Record<string, unknown>
  const id = text(item.id ?? item.key ?? item.language ?? key, '')
  if (!id) return null
  const name = text(item.name ?? item.label ?? item.display_name ?? item.language, id.replace(/[-_]/g, ' '))
  const status = text(item.status ?? (item.supported === true ? 'supported' : item.supported === false ? 'planned' : ''), 'unknown')
  const capabilities = item.capabilities && typeof item.capabilities === 'object' ? item.capabilities as Record<string, unknown> : {}
  return {
    id,
    name,
    extensions: list(item.extensions ?? item.file_extensions ?? item.suffixes),
    status,
    detection: text(item.detection ?? capabilities.detection, status),
    syntax: text(item.syntax ?? capabilities.syntax, status),
    analysis: text(item.analysis ?? capabilities.analysis, status),
    diagnostics: text(item.diagnostics ?? capabilities.diagnostics, status),
    test_generation: text(item.test_generation ?? item.testGeneration ?? capabilities.test_generation, 'not-configured'),
    execution: text(item.execution ?? capabilities.execution, status),
    notes: text(item.notes ?? item.description, ''),
  }
}

export function normalizeLanguages(payload: LanguagesResponse): LanguageSupport[] {
  const values = Array.isArray(payload)
    ? payload.map((item) => normalizeLanguage(item))
    : Object.entries(payload.languages ?? payload.supported ?? {}).map(([key, item]) => normalizeLanguage(item, key))
  return values.filter((item): item is LanguageSupport => item !== null)
}

function statusLabel(value: string): string {
  return value.replace(/[-_]/g, ' ')
}

function statusTone(value: string): string {
  const normalized = value.toLowerCase()
  if (normalized.includes('unavailable') || normalized.includes('unsupported') || normalized.includes('not-support') || normalized.includes('fail')) return 'danger'
  if (normalized.includes('support') || normalized.includes('ready') || normalized.includes('pass')) return 'success'
  if (normalized.includes('plan') || normalized.includes('partial')) return 'warning'
  return 'neutral'
}

export function LanguageMatrix() {
  const [languages, setLanguages] = useState<LanguageSupport[]>(FALLBACK_LANGUAGES)
  const [usingFallback, setUsingFallback] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    api.languages()
      .then((payload) => {
        const next = normalizeLanguages(payload)
        if (!active) return
        if (next.length) setLanguages(next)
        else setUsingFallback(true)
      })
      .catch(() => {
        if (active) setUsingFallback(true)
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => { active = false }
  }, [])

  return (
    <section className="workspace-panel language-panel" aria-labelledby="language-matrix-title">
      <div className="panel-heading">
        <div>
          <div className="panel-kicker">SOURCE SUPPORT</div>
          <h2 id="language-matrix-title">Supported languages</h2>
        </div>
         <span className="panel-count">{loading ? 'checking…' : `${languages.length} adapters`}</span>
      </div>
      <p className="language-intro">Language detection is recorded during source inspection. Availability can differ for analysis and isolated execution.</p>
       <div className="language-table" role="table" aria-label="Supported language matrix">
         <div className="language-table-head" role="row">
           <span role="columnheader">Language</span><span role="columnheader">Detection</span><span role="columnheader">Syntax</span><span role="columnheader">Static analysis</span><span role="columnheader">Diagnostics</span><span role="columnheader">Test generation</span><span role="columnheader">Execution</span>
         </div>
        {languages.map((language) => (
          <div className="language-row" role="row" key={language.id}>
             <div role="cell"><strong>{language.name}</strong><small>{language.extensions.length ? language.extensions.join(' · ') : 'extension rules from API'}</small></div>
             <span className={`language-status language-status--${statusTone(language.detection)}`} role="cell">{statusLabel(language.detection)}</span>
             <span className={`language-status language-status--${statusTone(language.syntax || language.detection)}`} role="cell">{statusLabel(language.syntax || language.detection)}</span>
             <span className={`language-status language-status--${statusTone(language.analysis)}`} role="cell">{statusLabel(language.analysis)}</span>
             <span className={`language-status language-status--${statusTone(language.diagnostics || language.analysis)}`} role="cell">{statusLabel(language.diagnostics || language.analysis)}</span>
             <span className={`language-status language-status--${statusTone(language.test_generation || 'not-configured')}`} role="cell">{statusLabel(language.test_generation || 'not-configured')}</span>
             <span className={`language-status language-status--${statusTone(language.execution)}`} role="cell">{statusLabel(language.execution)}</span>
          </div>
        ))}
      </div>
      <p className="language-source" role="status">{usingFallback ? 'Language service unavailable — showing the built-in support baseline.' : 'Live support matrix from /api/languages.'}</p>
    </section>
  )
}
