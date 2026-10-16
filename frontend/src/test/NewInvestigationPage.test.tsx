import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { NewInvestigationPage } from '../pages/NewInvestigationPage'

const sample = {
  id: 'simple-reproducible-bug',
  name: 'Checkout tax calculator',
  description: 'A reproducible type bug.',
  category: 'simple-reproducible-bug',
  exception_type: 'TypeError',
  traceback: 'TypeError: bad operands',
  file_count: 4,
  metadata: {},
}

describe('new investigation workflow', () => {
  beforeEach(() => {
      vi.stubGlobal('fetch', vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => [sample] })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ provider: 'github', configured: false, connected: false, message: 'not configured' }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ id: 'new-record' }) }))
  })

  it('selects a bundled sample, validates a title, and navigates after analysis', async () => {
    const user = userEvent.setup()
    render(<MemoryRouter initialEntries={['/app/new']}><Routes><Route path="/app/new" element={<NewInvestigationPage />} /><Route path="/app/investigations/:id" element={<div>analysis record opened</div>} /></Routes></MemoryRouter>)
    await user.click(await screen.findByRole('button', { name: /checkout tax calculator/i }))
    await user.type(screen.getByPlaceholderText(/e\.g\. checkout tax calculation/i), 'Sample investigation')
    await user.click(screen.getByRole('button', { name: /analyze investigation/i }))
    expect(await screen.findByText('analysis record opened')).toBeInTheDocument()
    expect(vi.mocked(fetch)).toHaveBeenCalledTimes(3)
  })
})
