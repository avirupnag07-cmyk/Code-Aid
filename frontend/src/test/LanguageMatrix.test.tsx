import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { LanguageMatrix } from '../components/LanguageMatrix'

describe('language support matrix', () => {
  afterEach(() => { cleanup(); vi.unstubAllGlobals() })

  it('renders the live language and capability statuses returned by the API', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ languages: [
        { id: 'python', name: 'Python', extensions: ['.py'], status: 'supported', detection: 'supported', analysis: 'supported', execution: 'docker' },
        { id: 'ruby', name: 'Ruby', extensions: ['.rb'], status: 'planned', detection: 'planned', analysis: 'planned', execution: 'unavailable' },
      ] }),
    }))

    render(<LanguageMatrix />)

    expect(await screen.findByText('Ruby')).toBeInTheDocument()
    expect(screen.getByText('Live support matrix from /api/languages.')).toBeInTheDocument()
    expect(screen.getByText('docker')).toBeInTheDocument()
    expect(screen.getByText('unavailable')).toBeInTheDocument()
  })

  it('keeps a useful baseline when the language endpoint is unavailable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))

    render(<LanguageMatrix />)

    expect(await screen.findByText('Language service unavailable — showing the built-in support baseline.')).toBeInTheDocument()
    expect(screen.getByText('Python')).toBeInTheDocument()
    expect(screen.getByText('JavaScript')).toBeInTheDocument()
  })
})
