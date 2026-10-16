import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { NewInvestigationPage } from '../pages/NewInvestigationPage'

describe('new investigation workflow', () => {
  afterEach(cleanup)

  beforeEach(() => {
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ id: 'new-record' }) }))
  })

  it('requires a ZIP upload, validates a title, and navigates after analysis', async () => {
    const user = userEvent.setup()
    render(<MemoryRouter initialEntries={['/app/new']}><Routes><Route path="/app/new" element={<NewInvestigationPage />} /><Route path="/app/investigations/:id" element={<div>analysis record opened</div>} /></Routes></MemoryRouter>)
    expect(screen.getByText(/zip archives are the only project import/i)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /public git/i })).not.toBeInTheDocument()
    expect(screen.queryByText(/github/i)).not.toBeInTheDocument()
    await user.type(screen.getByPlaceholderText(/e\.g\. checkout tax calculation/i), 'ZIP investigation')
    await user.click(screen.getByRole('button', { name: /analyze investigation/i }))
    expect(screen.getByRole('alert')).toHaveTextContent(/choose a zip archive/i)

    const archive = new File(['zip bytes'], 'project.zip', { type: 'application/zip' })
    await user.upload(screen.getByLabelText(/upload a project zip/i), archive)
    await user.click(screen.getByRole('button', { name: /analyze investigation/i }))
    expect(await screen.findByText('analysis record opened')).toBeInTheDocument()
    expect(vi.mocked(fetch)).toHaveBeenCalledTimes(1)
  })

  it('accepts a ZIP upload and sends no repository fields', async () => {
    const user = userEvent.setup()
    render(<MemoryRouter initialEntries={['/app/new']}><Routes><Route path="/app/new" element={<NewInvestigationPage />} /><Route path="/app/investigations/:id" element={<div>analysis record opened</div>} /></Routes></MemoryRouter>)
    const archive = new File(['zip bytes'], 'project.zip', { type: 'application/zip' })
    await user.upload(screen.getByLabelText(/upload a project zip/i), archive)
    await user.type(screen.getByPlaceholderText(/e\.g\. checkout tax calculation/i), 'ZIP investigation')
    await user.click(screen.getByRole('button', { name: /analyze investigation/i }))

    expect(await screen.findByText('analysis record opened')).toBeInTheDocument()
    const request = vi.mocked(fetch).mock.calls[0]?.[1]
    const body = request?.body as FormData
    expect(body.get('archive')).toBe(archive)
    expect(body.has('repository_url')).toBe(false)
    expect(body.has('ref')).toBe(false)
    expect(body.has('subdirectory')).toBe(false)
  })
})
