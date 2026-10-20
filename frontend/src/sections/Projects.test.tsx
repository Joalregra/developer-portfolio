import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
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

  it('links the live demo of Gedocs and shows its screens with captions', () => {
    renderWithProviders(<Projects />, 'es')
    const gedocs = screen.getByRole('article', { name: 'Gedocs' })
    expect(within(gedocs).getByText('En producción')).toBeInTheDocument()
    const link = within(gedocs).getByRole('link', { name: /Abrir la demo de Gedocs/ })
    expect(link).toHaveAttribute('href', 'https://gedocs.johanrendon.com/')
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', expect.stringContaining('noopener'))
    expect(within(gedocs).getAllByRole('img')).toHaveLength(4)
    expect(within(gedocs).getAllByRole('figure')).toHaveLength(4)
    expect(within(gedocs).getByText(/datos ficticios/)).toBeInTheDocument()
  })

  it('gives every demo screenshot a text alternative in both languages', () => {
    for (const locale of ['es', 'en'] as const) {
      const { unmount } = renderWithProviders(<Projects />, locale)
      const gedocs = screen.getByRole('article', { name: 'Gedocs' })
      for (const image of within(gedocs).getAllByRole('img')) {
        expect(image.getAttribute('alt')?.length ?? 0).toBeGreaterThan(20)
      }
      unmount()
    }
  })

  it('expands a screenshot, moves between images and closes with Escape', async () => {
    const user = userEvent.setup()
    renderWithProviders(<Projects />, 'es')
    const gedocs = screen.getByRole('article', { name: 'Gedocs' })
    const openers = within(gedocs).getAllByRole('button', { name: /^Ampliar imagen:/ })
    expect(openers).toHaveLength(4)
    expect(screen.queryByRole('dialog')).toBeNull()

    await user.click(openers[0])
    const dialog = screen.getByRole('dialog', { name: 'Vista ampliada de la imagen' })
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    expect(within(dialog).getByText('1 de 4')).toBeInTheDocument()
    expect(within(dialog).getByRole('button', { name: 'Cerrar la vista ampliada' })).toHaveFocus()

    await user.click(within(dialog).getByRole('button', { name: 'Imagen siguiente' }))
    expect(within(dialog).getByText('2 de 4')).toBeInTheDocument()
    await user.keyboard('{ArrowLeft}{ArrowLeft}')
    expect(within(dialog).getByText('4 de 4')).toBeInTheDocument()

    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(openers[3]).toHaveFocus()
  })

  it('closes the enlarged image from its button', async () => {
    const user = userEvent.setup()
    renderWithProviders(<Projects />, 'en')
    const gedocs = screen.getByRole('article', { name: 'Gedocs' })
    await user.click(within(gedocs).getAllByRole('button', { name: /^Enlarge image:/ })[1])
    const dialog = screen.getByRole('dialog', { name: 'Enlarged image' })
    expect(within(dialog).getByText('2 of 4')).toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: 'Close the enlarged view' }))
    expect(screen.queryByRole('dialog')).toBeNull()
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
    const diagrams = screen.getAllByRole('img').filter((el) => el.tagName.toLowerCase() === 'svg')
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
