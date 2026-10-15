import { useCallback, useSyncExternalStore } from 'react'
import { readStorage, writeStorage } from '../lib/storage'

export type Theme = 'light' | 'dark'
const THEME_KEY = 'theme'

const listeners = new Set<() => void>()

function systemTheme(): Theme {
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function currentTheme(): Theme {
  const stored = readStorage('local', THEME_KEY)
  return stored === 'light' || stored === 'dark' ? stored : systemTheme()
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  const query = window.matchMedia?.('(prefers-color-scheme: dark)')
  query?.addEventListener('change', listener)
  return () => {
    listeners.delete(listener)
    query?.removeEventListener('change', listener)
  }
}

/**
 * Follows the system theme until the visitor picks one; the pick is then saved.
 * The store is shared, so every toggle on the page shows the same state.
 */
export function useTheme() {
  const theme = useSyncExternalStore(subscribe, currentTheme, () => 'light' as Theme)

  const toggle = useCallback(() => {
    const next: Theme = currentTheme() === 'dark' ? 'light' : 'dark'
    writeStorage('local', THEME_KEY, next)
    document.documentElement.dataset.theme = next
    listeners.forEach((listener) => listener())
  }, [])

  return { theme, toggle }
}
