import { describe, expect, it } from 'vitest'
import { localeFromPath, pathForLocale, resolveInitialLocale } from './locale'

const base = { pathname: '/', stored: null, languages: [] as string[] }

describe('resolveInitialLocale', () => {
  it('uses the language in the URL first, so shared links keep their language', () => {
    expect(
      resolveInitialLocale({ ...base, pathname: '/en/', stored: 'es', languages: ['es-CO'] }),
    ).toBe('en')
    expect(resolveInitialLocale({ ...base, pathname: '/es/', stored: 'en' })).toBe('es')
  })

  it('then the saved preference', () => {
    expect(resolveInitialLocale({ ...base, stored: 'en', languages: ['es-CO'] })).toBe('en')
  })

  it('ignores an invalid saved value', () => {
    expect(resolveInitialLocale({ ...base, stored: 'fr', languages: ['es'] })).toBe('es')
  })

  it('treats any Spanish variant as Spanish', () => {
    for (const language of ['es', 'es-CO', 'es-MX', 'ES-ar']) {
      expect(resolveInitialLocale({ ...base, languages: [language] })).toBe('es')
    }
  })

  it('checks every browser language, not only the first', () => {
    expect(resolveInitialLocale({ ...base, languages: ['fr-FR', 'es-ES'] })).toBe('es')
  })

  it('falls back to English', () => {
    expect(resolveInitialLocale({ ...base, languages: ['fr-FR', 'de'] })).toBe('en')
    expect(resolveInitialLocale(base)).toBe('en')
  })
})

describe('locale paths', () => {
  it('reads the language from the first path segment', () => {
    expect(localeFromPath('/es/')).toBe('es')
    expect(localeFromPath('/en/something')).toBe('en')
    expect(localeFromPath('/')).toBeNull()
    expect(localeFromPath('/fr/')).toBeNull()
  })

  it('builds the path of each language', () => {
    expect(pathForLocale('es')).toBe('/es/')
    expect(pathForLocale('en')).toBe('/en/')
  })
})
