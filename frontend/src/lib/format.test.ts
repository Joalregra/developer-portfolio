import { describe, expect, it } from 'vitest'
import { formatLongMonth, formatMonthRange } from './format'

describe('date formatting', () => {
  it('writes the month as text in Spanish', () => {
    const range = formatMonthRange('2026-04', '2026-10', 'es')
    expect(range).toMatch(/abr/i)
    expect(range).toMatch(/oct/i)
    expect(range).toContain('2026')
    expect(range).toContain('–')
  })

  it('writes the month as text in English', () => {
    expect(formatMonthRange('2026-04', '2026-10', 'en')).toBe('Apr 2026 – Oct 2026')
  })

  it('does not depend on the local time zone', () => {
    expect(formatMonthRange('2024-07', '2026-04', 'en')).toBe('Jul 2024 – Apr 2026')
  })

  it('formats the long month for the footer', () => {
    expect(formatLongMonth('2026-10', 'en')).toBe('October 2026')
    expect(formatLongMonth('2026-10', 'es')).toBe('octubre de 2026')
  })
})
