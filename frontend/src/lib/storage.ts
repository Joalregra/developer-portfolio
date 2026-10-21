type Kind = 'local' | 'session'

// Storage can be missing or throw (private windows, blocked site data), so every access is guarded.
function getStore(kind: Kind): Storage | null {
  try {
    return kind === 'local' ? window.localStorage : window.sessionStorage
  } catch {
    return null
  }
}

export function readStorage(kind: Kind, key: string): string | null {
  try {
    return getStore(kind)?.getItem(key) ?? null
  } catch {
    return null
  }
}

export function writeStorage(kind: Kind, key: string, value: string): void {
  try {
    getStore(kind)?.setItem(key, value)
  } catch {
    // Quota or privacy errors: the page keeps working without persistence.
  }
}

export function removeStorage(kind: Kind, key: string): void {
  try {
    getStore(kind)?.removeItem(key)
  } catch {
    // Same as above.
  }
}
