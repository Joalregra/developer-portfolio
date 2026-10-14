import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Hero } from './Hero'
import { profile } from '../data/profile'

describe('Hero', () => {
  it('shows the name and the role in Spanish by default', () => {
    render(<Hero />)
    expect(screen.getByRole('heading', { level: 1, name: profile.name })).toBeInTheDocument()
    expect(screen.getByText(profile.role.es)).toBeInTheDocument()
  })

  it('links to the CV as a download', () => {
    render(<Hero locale="en" />)
    const cvLink = screen.getByRole('link', { name: 'Download CV' })
    expect(cvLink).toHaveAttribute('href', profile.links.cv)
    expect(cvLink).toHaveAttribute('download')
  })
})
