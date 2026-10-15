import { locales, type Locale } from '../data/profile'

export const LOCALE_KEY = 'locale'

export function isLocale(value: unknown): value is Locale {
  return typeof value === 'string' && (locales as readonly string[]).includes(value)
}

export function localeFromPath(pathname: string): Locale | null {
  const segment = pathname.split('/')[1]
  return isLocale(segment) ? segment : null
}

/**
 * Initial language (I18N-05): the URL wins so shared links keep their language,
 * then the saved preference, then the browser languages (any `es*` is Spanish), then English.
 */
export function resolveInitialLocale(input: {
  pathname: string
  stored: string | null
  languages: readonly string[]
}): Locale {
  const fromPath = localeFromPath(input.pathname)
  if (fromPath) return fromPath
  if (isLocale(input.stored)) return input.stored
  if (input.languages.some((language) => language.toLowerCase().startsWith('es'))) return 'es'
  return 'en'
}

export function pathForLocale(locale: Locale): string {
  return `/${locale}/`
}
