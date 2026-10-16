import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { InvestigationPage } from '../pages/InvestigationPage'

const investigation = {
  id: 'investigation-1',
  title: 'Tax calculation failure',
  status: 'analyzed',
  source_type: 'sample',
  sample_id: 'simple-reproducible-bug',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  finding_count: 1,
  hypothesis_count: 1,
  source: {
    source_type: 'sample',
    sample_id: 'simple-reproducible-bug',
    file_count: 1,
    traceback: 'TypeError: unsupported operand type(s)',
    metadata: { detected_language: 'Python', exception_type: 'TypeError' },
    intake: {},
    files: [{ path: 'calculator.py', kind: 'python', size: 128 }],
  },
  results: {
    facts: [{ text: 'The failing call receives a string rate.', evidence: [] }],
    findings: [{ text: 'A numeric operation receives incompatible values.', severity: 'high', rule_id: 'mixed-operation', evidence: [] }],
    hypotheses: [{ text: 'The rate should be normalized before arithmetic.', score: 0.8, rationale: 'The traceback points at the arithmetic expression.', evidence: [] }],
    generated_tests: [{ path: 'tests/test_repro.py', content: 'def test_repro():\n    assert True', purpose: 'Reproduce the reported failure', validation_status: 'valid', validation_message: '', test_mode: 'exception-reproduction' }],
    execution_results: [],
    verification: { status: 'not-run', changed: false, safe_to_apply: false, diff: '', message: '', checks: [] },
  },
}

const executedInvestigation = {
  ...investigation,
  status: 'tests-passed',
  results: {
    ...investigation.results,
    execution_results: [{ status: 'passed', exit_code: 0, stdout: '1 passed', stderr: '', duration_ms: 42, reason: 'Generated test process exited successfully.', command: ['pytest'], started_at: '2026-01-01T00:00:00Z' }],
  },
}

describe('investigation status workflow', () => {
  afterEach(() => { cleanup(); vi.unstubAllGlobals() })

  it('separates evidence stages and records an isolated execution receipt', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => investigation })
      .mockResolvedValueOnce({ ok: true, json: async () => executedInvestigation }))

    render(<MemoryRouter initialEntries={['/app/investigations/investigation-1']}><Routes><Route path="/app/investigations/:id" element={<InvestigationPage />} /></Routes></MemoryRouter>)

    expect(await screen.findByRole('heading', { name: 'Keep each claim in its lane' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Facts: 1 observed/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Findings: 1 linked/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Hypotheses: 1 ranked/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Tests: 1 generated/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Execution: not run/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Verification: not checked/i })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /Execution: not run/i }))
    await user.click(screen.getByRole('button', { name: /Run in isolation/i }))

    expect(await screen.findByText('Generated test process exited successfully.')).toBeInTheDocument()
    expect(screen.getByText('1 passed')).toBeInTheDocument()
    expect(screen.getByText('passed')).toBeInTheDocument()
  })
})
