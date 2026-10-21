import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'

afterEach(() => {
  window.localStorage.clear()
  window.history.replaceState(null, '', '/')
  vi.restoreAllMocks()
})

describe('App', () => {
  it('has one h1, a skip link and the sections in the intended order', () => {
    const { container } = render(<App initialLocale="es" />)
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
    expect(screen.getByRole('link', { name: 'Saltar al contenido' })).toHaveAttribute(
      'href',
      '#main',
    )

    const ids = Array.from(container.querySelectorAll('main > section')).map((s) => s.id)
    expect(ids).toEqual([
      'top',
      'projects',
      'experience',
      'about',
      'skills',
      'education',
      'contact',
    ])
  })

  it('names every section through its heading', () => {
    render(<App initialLocale="en" />)
    for (const name of [
      'Projects',
      'Experience',
      'About',
      'Skills',
      'Education and certifications',
      'Contact',
    ]) {
      expect(screen.getByRole('region', { name })).toBeInTheDocument()
    }
  })

  it('has no emoji and no progress-bar style skill levels', () => {
    const { container } = render(<App initialLocale="es" />)
    expect(container.textContent).not.toMatch(/\p{Extended_Pictographic}/u)
    expect(container.querySelector('[role="progressbar"], progress, meter')).toBeNull()
  })

  it('lists certifications without empty verification buttons', () => {
    render(<App initialLocale="es" />)
    const region = screen.getByRole('region', { name: 'Formación y certificaciones' })
    expect(region).toHaveTextContent('AI Fluency: Framework & Foundations')
    expect(region).toHaveTextContent('Puntaje: 99,6 / 100')
    expect(region.querySelectorAll('button')).toHaveLength(0)
    const verify = screen.getAllByRole('link', { name: /Verificar certificado/ })
    expect(verify).toHaveLength(1)
    expect(verify[0]).toHaveAttribute(
      'href',
      'https://academy.claude.com/verify/71f83beb90b7405c3d910d2a41ab38ef',
    )
    expect(verify[0]).toHaveAttribute('target', '_blank')
    const pdfs = Array.from(region.querySelectorAll<HTMLAnchorElement>('a[href^="/certs/"]'))
    expect(pdfs).toHaveLength(7)
    for (const link of pdfs) {
      expect(link).toHaveAttribute('target', '_blank')
      expect(link).toHaveAttribute('rel', 'noopener noreferrer')
      expect(link.getAttribute('href')).toMatch(/^\/certs\/[a-z-]+\.pdf$/)
    }
    expect(region.textContent).not.toContain('PENDIENTE')
  })

  it('groups skills by evidence', () => {
    render(<App initialLocale="es" />)
    for (const name of [
      'Usado en producción',
      'Usado en proyectos',
      'Aprendiendo ahora',
      'Herramientas',
    ]) {
      expect(screen.getByRole('heading', { name })).toBeInTheDocument()
    }
  })

  it('keeps the whole page in one language', async () => {
    const user = userEvent.setup()
    const { container } = render(<App initialLocale="es" />)
    await user.click(screen.getByRole('button', { name: 'EN, English' }))
    const text = container.textContent ?? ''
    expect(text).toContain('Available for immediate hiring')
    expect(text).not.toContain('Disponible para contratación')
    expect(text).not.toContain('Descargar CV')
  })

  it('copies the email and announces it in a polite live region', async () => {
    const user = userEvent.setup()
    const writeText = vi.spyOn(navigator.clipboard, 'writeText').mockResolvedValue()
    render(<App initialLocale="es" />)
    await user.click(screen.getByRole('button', { name: 'Copiar correo' }))
    expect(writeText).toHaveBeenCalledWith('johanalexis808@gmail.com')
    const status = await screen.findByText('Correo copiado')
    expect(status).toHaveAttribute('aria-live', 'polite')
  })

  it('tells the visitor when copying fails', async () => {
    const user = userEvent.setup()
    vi.spyOn(navigator.clipboard, 'writeText').mockRejectedValue(new Error('denied'))
    render(<App initialLocale="en" />)
    await user.click(screen.getByRole('button', { name: 'Copy email' }))
    expect(await screen.findByText(/Could not copy/)).toBeInTheDocument()
  })

  it('persists the chosen theme', async () => {
    const user = userEvent.setup()
    render(<App initialLocale="es" />)
    const toggle = screen.getAllByRole('button', { name: 'Cambiar a tema oscuro' })[0]
    await user.click(toggle)
    expect(window.localStorage.getItem('theme')).toBe('dark')
    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(screen.getAllByRole('button', { name: 'Cambiar a tema claro' }).length).toBeGreaterThan(
      0,
    )
    delete document.documentElement.dataset.theme
  })
})
