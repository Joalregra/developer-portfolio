import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { renderWithProviders } from '../test/render'
import { Experience } from './Experience'

describe('Experience: recommendation letter', () => {
  it('shows the translated quote, its author and the original-language note in Spanish', () => {
    renderWithProviders(<Experience />, 'es')

    const letter = screen.getByRole('figure', { name: 'Carta de recomendación' })
    expect(letter).toHaveTextContent('Johan demostró una notable competencia técnica')
    expect(letter).toHaveTextContent('Pablo Lecea, Games Director en Globant.')
    expect(letter).toHaveTextContent('Carta original en inglés.')
  })

  it('shows the verbatim quote in English, without the translation note', () => {
    renderWithProviders(<Experience />, 'en')

    const letter = screen.getByRole('figure', { name: 'Recommendation letter' })
    expect(letter).toHaveTextContent('Johan demonstrated notable technical proficiency')
    expect(letter).toHaveTextContent('Pablo Lecea, Games Director, Globant.')
    expect(letter).not.toHaveTextContent('Original letter in English')
  })

  it('does not link to the signed PDF while it is not published', () => {
    renderWithProviders(<Experience />, 'en')

    const letter = screen.getByRole('figure', { name: 'Recommendation letter' })
    expect(letter.querySelector('a[href*=".pdf"]')).toBeNull()
    expect(document.querySelector('a[href*="letters"]')).toBeNull()
  })

  it('offers to put visitors in touch with the author through Johan, not directly', () => {
    renderWithProviders(<Experience />, 'en')

    const letter = screen.getByRole('figure', { name: 'Recommendation letter' })
    expect(letter).toHaveTextContent('Pablo can confirm this letter.')
    const email = within(letter).getByRole('link', { name: 'johanalexis808@gmail.com' })
    expect(email).toHaveAttribute('href', 'mailto:johanalexis808@gmail.com')
    expect(letter.textContent).not.toMatch(/globant\.com|linkedin/i)
  })
})
