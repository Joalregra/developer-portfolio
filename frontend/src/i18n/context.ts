import { createContext } from 'react'
import type { Locale } from '../data/profile'
import type { Messages } from './es'

export interface LocaleContextValue {
  locale: Locale
  setLocale: (locale: Locale) => void
  t: Messages
}

export const LocaleContext = createContext<LocaleContextValue | null>(null)
