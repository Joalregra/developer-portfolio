import { useContext } from 'react'
import { LocaleContext, type LocaleContextValue } from '../i18n/context'

export function useLocale(): LocaleContextValue {
  const value = useContext(LocaleContext)
  if (!value) throw new Error('useLocale must be used inside <LocaleProvider>')
  return value
}
