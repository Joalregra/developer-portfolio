import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { profile } from '../data/profile'
import { renderWithProviders } from '../test/render'
import { Hero } from './Hero'

describe('Hero', () => {
  it('shows the name as the only h1 and the exact role in Spanish', () => {
    renderWithProviders(<Hero />)
    const headings = screen.getAllByRole('heading', { level: 1 })
    expect(headings).toHaveLength(1)
    expect(headings[0]).toHaveTextContent(profile.name)
    expect(screen.getByText(profile.role.es)).toBeInTheDocument()
  })

  it('shows location with time zone and availability as text (HERO-01)', () => {
    renderWithProviders(<Hero />, 'en')
    expect(screen.getByText('San José, Caldas, Colombia (GMT-5)')).toBeInTheDocument()
    expect(
      screen.getByText('Available for immediate hiring. Remote or hybrid.'),
    ).toBeInTheDocument()
  })

  it('has one primary action and links the CV of the active language', () => {
    renderWithProviders(<Hero />, 'es')
    const cv = screen.getByRole('link', { name: /Descargar CV/ })
    expect(cv).toHaveAttribute('href', profile.cv.es.href)
    expect(cv).toHaveAttribute('download')
    expect(cv).toHaveTextContent('PDF, 1 página')
    expect(screen.getByRole('link', { name: 'Contactar' })).toHaveAttribute(
      'href',
      `mailto:${profile.email}`,
    )
  })

  it('uses the English CV in English', () => {
    renderWithProviders(<Hero />, 'en')
    expect(screen.getByRole('link', { name: /Download CV/ })).toHaveAttribute(
      'href',
      profile.cv.en.href,
    )
  })

  it('marks external links as opening in a new tab', () => {
    renderWithProviders(<Hero />, 'en')
    const linkedin = screen.getByRole('link', { name: /LinkedIn/ })
    expect(linkedin).toHaveAttribute('target', '_blank')
    expect(linkedin).toHaveAttribute('rel', 'noopener noreferrer')
    expect(linkedin).toHaveTextContent('(opens in a new tab)')
  })

  it('offers the assistant with three suggested questions', () => {
    renderWithProviders(<Hero />, 'es')
    expect(screen.getByLabelText('Tu pregunta')).toBeInTheDocument()
    const group = screen.getByRole('group', { name: 'Preguntas sugeridas' })
    expect(group.querySelectorAll('button')).toHaveLength(3)
  })

  it('shows the photo with a translated alt text and explicit size', () => {
    renderWithProviders(<Hero />, 'en')
    const photo = screen.getByRole('img', { name: 'Photo of Johan Rendon' })
    expect(photo).toHaveAttribute('width', '240')
    expect(photo).toHaveAttribute('height', '320')
    expect(photo.getAttribute('src')).toMatch(/\.webp$/)
  })
})
