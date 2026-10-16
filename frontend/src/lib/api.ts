import type {
  CreateInvestigationInput,
  ExecutionResult,
  Investigation,
  InvestigationSummary,
  LanguagesResponse,
  Sample,
  VerificationResult,
} from './types'

const API_PREFIX = import.meta.env.VITE_API_URL || '/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_PREFIX}${path}`, {
    headers: { Accept: 'application/json', ...(init?.headers || {}) },
    ...init,
  })
  if (!response.ok) {
    let message = `Request failed (${response.status})`
    try {
      const body = await response.json() as { detail?: string }
      if (body.detail) message = body.detail
    } catch {
      // Keep the status message when a proxy returns a non-JSON error.
    }
    throw new Error(message)
  }
  return response.json() as Promise<T>
}

export const api = {
  health: () => request<{ status: string; service: string; version: string; database: string }>('/health'),
  languages: () => request<LanguagesResponse>('/languages'),
  samples: () => request<Sample[]>('/samples'),
  investigations: () => request<InvestigationSummary[]>('/investigations'),
  investigation: (id: string) => request<Investigation>(`/investigations/${encodeURIComponent(id)}`),
  deleteInvestigation: (id: string) => request<{ deleted: boolean; id: string }>(`/investigations/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  createInvestigation: async (input: CreateInvestigationInput) => {
    const body = new FormData()
    if (input.title.trim()) body.append('title', input.title.trim())
    if (input.bugDescription.trim()) body.append('bug_description', input.bugDescription.trim())
    if (input.traceback.trim()) body.append('traceback', input.traceback)
    if (input.reproductionSteps.trim()) body.append('reproduction_steps', input.reproductionSteps.trim())
    if (input.expectedBehavior.trim()) body.append('expected_behavior', input.expectedBehavior.trim())
    if (input.actualBehavior.trim()) body.append('actual_behavior', input.actualBehavior.trim())
    if (input.environment.trim()) body.append('environment', input.environment.trim())
    if (input.sampleId) body.append('sample_id', input.sampleId)
    if (input.archive) body.append('archive', input.archive)
    return request<Investigation>('/investigations', { method: 'POST', body })
  },
  runTests: (id: string, timeoutSeconds?: number) => request<Investigation & { execution_result: ExecutionResult }>(`/investigations/${encodeURIComponent(id)}/run-tests`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(timeoutSeconds ? { timeout_seconds: timeoutSeconds } : {}),
  }),
  verifyPatch: (id: string, filePath: string, content: string) => request<Investigation & { verification: VerificationResult }>(`/investigations/${encodeURIComponent(id)}/verify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ file_path: filePath, content }),
  }),
  reportUrl: (id: string) => `${API_PREFIX}/investigations/${encodeURIComponent(id)}/report`,
}

export function formatDate(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', year: 'numeric' }).format(date)
}

export function formatRelativeDate(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const delta = Date.now() - date.getTime()
  const hours = Math.floor(delta / 3_600_000)
  if (hours < 1) return 'just now'
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 7) return `${days}d ago`
  return formatDate(value)
}
