import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import App from '../App'

describe('Code-Aid landing page', () => {
  it('communicates the product promise and offers a real workspace path', () => {
    window.history.pushState({}, '', '/')
    render(<App />)
    expect(screen.getByRole('heading', { name: /from vague bug reports/i })).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: /start an investigation/i }).every((link) => link.getAttribute('href') === '/app/new')).toBe(true)
  })
})
