import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import type { Locale } from '../data/profile'
import { readStorage, writeStorage } from '../lib/storage'
import { LocaleContext } from './context'
import { en } from './en'
import { es } from './es'
import { LOCALE_KEY, pathForLocale, resolveInitialLocale } from './locale'
import { siteMeta } from './meta'

const messages = { es, en }

interface LocaleProviderProps {
  children: ReactNode
  /** Forces the language (used by tests); otherwise it comes from the URL, storage or the browser. */
  initialLocale?: Locale
}

function detectLocale(): Locale {
  return resolveInitialLocale({
    pathname: window.location.pathname,
    stored: readStorage('local', LOCALE_KEY),
    languages: navigator.languages?.length ? navigator.languages : [navigator.language ?? ''],
  })
}

function syncDocument(locale: Locale) {
  document.documentElement.lang = locale
  document.title = siteMeta[locale].title
  document
    .querySelector('meta[name="description"]')
    ?.setAttribute('content', siteMeta[locale].description)
}

interface ScrollAnchor {
  id: string
  top: number
}

/** The section or case study sitting under the header, so its position can be restored. */
function captureScrollAnchor(): ScrollAnchor | null {
  const line = document.querySelector('header')?.getBoundingClientRect().bottom ?? 0
  let found: ScrollAnchor | null = null
  // Later matches are nested deeper (a case study inside the projects section), so they win.
  document
    .querySelectorAll<HTMLElement>('main section[id], main article[id]')
    .forEach((element) => {
      const rect = element.getBoundingClientRect()
      if (rect.top <= line + 8 && rect.bottom > line) found = { id: element.id, top: rect.top }
    })
  return found
}

export function LocaleProvider({ children, initialLocale }: LocaleProviderProps) {
  const [locale, setLocaleState] = useState<Locale>(() => initialLocale ?? detectLocale())
  const anchor = useRef<ScrollAnchor | null>(null)

  // Texts differ in length between languages, so keep the section the reader was on (I18N-03).
  useLayoutEffect(() => {
    const saved = anchor.current
    anchor.current = null
    const element = saved && document.getElementById(saved.id)
    if (saved && element) {
      window.scrollBy({ top: element.getBoundingClientRect().top - saved.top, behavior: 'instant' })
    }
    // Browser scroll anchoring was switched off in setLocale so it does not add its own correction.
    window.requestAnimationFrame(() =>
      document.documentElement.style.removeProperty('overflow-anchor'),
    )
  }, [locale])

  useEffect(() => {
    syncDocument(locale)
    // Each language has its own URL; the hash is kept so the reader stays in the same section.
    const target = pathForLocale(locale)
    if (window.location.pathname !== target) {
      window.history.replaceState(
        window.history.state,
        '',
        `${target}${window.location.search}${window.location.hash}`,
      )
    }
  }, [locale])

  const setLocale = useCallback((next: Locale) => {
    anchor.current = captureScrollAnchor()
    document.documentElement.style.setProperty('overflow-anchor', 'none')
    writeStorage('local', LOCALE_KEY, next)
    setLocaleState(next)
  }, [])

  const value = useMemo(() => ({ locale, setLocale, t: messages[locale] }), [locale, setLocale])

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>
}
