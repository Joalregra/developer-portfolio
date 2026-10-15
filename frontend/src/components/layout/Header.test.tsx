import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it } from 'vitest'
import { renderWithProviders } from '../../test/render'
import { Header } from './Header'

afterEach(() => {
  window.localStorage.clear()
  window.history.replaceState(null, '', '/')
})

describe('Header', () => {
  it('opens and closes the mobile menu with aria-expanded and Escape', async () => {
    const user = userEvent.setup()
    renderWithProviders(<Header />, 'es')
    const button = screen.getByRole('button', { name: 'Abrir menú' })
    expect(button).toHaveAttribute('aria-expanded', 'false')
    expect(button).toHaveAttribute('aria-controls', 'site-menu')

    await user.click(button)
    const open = screen.getByRole('button', { name: 'Cerrar menú' })
    expect(open).toHaveAttribute('aria-expanded', 'true')

    await user.keyboard('{Escape}')
    expect(screen.getByRole('button', { name: 'Abrir menú' })).toHaveAttribute(
      'aria-expanded',
      'false',
    )
    expect(screen.getByRole('button', { name: 'Abrir menú' })).toHaveFocus()
  })

  it('closes the menu when a link is chosen and when tapping outside', async () => {
    const user = userEvent.setup()
    renderWithProviders(<Header />, 'es')
    await user.click(screen.getByRole('button', { name: 'Abrir menú' }))
    await user.click(screen.getAllByRole('link', { name: 'Proyectos' })[0])
    expect(screen.getByRole('button', { name: 'Abrir menú' })).toHaveAttribute(
      'aria-expanded',
      'false',
    )

    await user.click(screen.getByRole('button', { name: 'Abrir menú' }))
    await user.click(document.body)
    expect(screen.getByRole('button', { name: 'Abrir menú' })).toHaveAttribute(
      'aria-expanded',
      'false',
    )
  })

  it('has the language switch as text with the active language marked', () => {
    renderWithProviders(<Header />, 'es')
    const spanish = screen.getByRole('button', { name: 'ES, Español' })
    const english = screen.getByRole('button', { name: 'EN, English' })
    expect(spanish).toHaveTextContent('ES')
    expect(english).toHaveTextContent('EN')
    expect(spanish).toHaveAttribute('aria-pressed', 'true')
    expect(english).toHaveAttribute('aria-pressed', 'false')
    expect(english).toHaveAttribute('lang', 'en')
  })

  it('changes language keeping the hash, and updates lang, title and the saved preference', async () => {
    const user = userEvent.setup()
    window.history.replaceState(null, '', '/es/#projects')
    renderWithProviders(<Header />, 'es')

    await user.click(screen.getByRole('button', { name: 'EN, English' }))

    expect(document.documentElement.lang).toBe('en')
    expect(document.title).toBe('Johan Rendon | Junior Backend Developer (Python, FastAPI)')
    expect(window.location.pathname).toBe('/en/')
    expect(window.location.hash).toBe('#projects')
    expect(window.localStorage.getItem('locale')).toBe('en')
    expect(screen.getByRole('button', { name: 'EN, English' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
  })

  it('exposes every section anchor once', () => {
    renderWithProviders(<Header />, 'en')
    const nav = screen.getByRole('navigation', { name: 'Main' })
    const hrefs = Array.from(nav.querySelectorAll('a')).map((a) => a.getAttribute('href'))
    expect(hrefs).toEqual([
      '#projects',
      '#experience',
      '#about',
      '#skills',
      '#education',
      '#contact',
    ])
  })
})
