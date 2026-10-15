import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { renderWithProviders } from '../test/render'
import { Projects } from './Projects'

describe('Projects', () => {
  it('lists the case studies in the intended order', () => {
    renderWithProviders(<Projects />, 'es')
    const titles = screen.getAllByRole('heading', { level: 3 }).map((h) => h.textContent)
    expect(titles).toEqual([
      'Plataforma de reportes de inteligencia de producto con IA',
      'Plataforma de inteligencia competitiva',
      'Gedocs',
    ])
  })

  it('shows the NDA status and the positive note, with no demo or code button', () => {
    renderWithProviders(<Projects />, 'en')
    const reports = screen.getByRole('article', { name: /AI product intelligence/ })
    expect(within(reports).getByText('Under NDA: no public code or demo')).toBeInTheDocument()
    expect(
      within(reports).getByText(/runs in production in the company's private environment/),
    ).toBeInTheDocument()
    expect(within(reports).queryByRole('link')).toBeNull()
    expect(within(reports).queryByRole('button', { name: /demo/i })).toBeNull()
  })

  it('does not claim production for the project whose status is not stated', () => {
    renderWithProviders(<Projects />, 'es')
    const intel = screen.getByRole('article', { name: /inteligencia competitiva/ })
    expect(within(intel).queryByText(/en producción en el entorno privado/)).toBeNull()
    expect(within(intel).getByText(/acuerdo de confidencialidad/)).toBeInTheDocument()
  })

  it('shows the pending demo of Gedocs as plain text, not as a disabled link', () => {
    renderWithProviders(<Projects />, 'es')
    const gedocs = screen.getByRole('article', { name: 'Gedocs' })
    expect(within(gedocs).getByText('Demo con datos de prueba en preparación')).toBeInTheDocument()
    expect(within(gedocs).getByText('En producción')).toBeInTheDocument()
    expect(within(gedocs).queryByRole('link')).toBeNull()
  })

  it('keeps the visible stack to 8 badges or fewer', () => {
    renderWithProviders(<Projects />, 'en')
    for (const article of screen.getAllByRole('article')) {
      const stack = within(article).getByRole('heading', { name: 'Stack' }).nextElementSibling
      expect(stack?.querySelectorAll('li').length).toBeLessThanOrEqual(8)
    }
  })

  it('draws the architecture diagram for the NDA projects as accessible SVG', () => {
    renderWithProviders(<Projects />, 'en')
    const diagrams = screen.getAllByRole('img')
    expect(diagrams).toHaveLength(2)
    const [first] = diagrams
    const labelledBy = (first.getAttribute('aria-labelledby') ?? '').split(' ')
    const [titleId, descId] = labelledBy
    expect(first.querySelector(`[id="${titleId}"]`)).toHaveTextContent(
      'Architecture of the AI reporting platform',
    )
    expect(first.querySelector(`[id="${descId}"]`)).toHaveTextContent(/Block diagram/)
  })

  it('has an ask-the-assistant button per project', () => {
    renderWithProviders(<Projects />, 'es')
    expect(
      screen.getAllByRole('button', { name: 'Pregúntale al asistente sobre este proyecto' }),
    ).toHaveLength(3)
  })
})
