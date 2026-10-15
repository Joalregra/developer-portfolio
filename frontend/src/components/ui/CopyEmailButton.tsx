import { useEffect, useRef, useState } from 'react'
import { useLocale } from '../../hooks/useLocale'
import { Button } from './Button'
import { CheckIcon, CopyIcon } from './icons'

type CopyState = 'idle' | 'copied' | 'failed'

export function CopyEmailButton({ email }: { email: string }) {
  const { t } = useLocale()
  const [state, setState] = useState<CopyState>('idle')
  const timer = useRef<number | undefined>(undefined)

  useEffect(() => () => window.clearTimeout(timer.current), [])

  async function copy() {
    let next: CopyState = 'copied'
    try {
      await navigator.clipboard.writeText(email)
    } catch {
      next = 'failed'
    }
    setState(next)
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => setState('idle'), 3000)
  }

  const message =
    state === 'copied' ? t.contact.copied : state === 'failed' ? t.contact.copyFailed : ''

  return (
    <>
      <Button variant="secondary" onClick={copy}>
        {state === 'copied' ? <CheckIcon /> : <CopyIcon />}
        {t.contact.copy}
      </Button>
      {/* The live region stays mounted so the confirmation is announced (CONT-01). */}
      <span role="status" aria-live="polite" className="text-sm text-ink-muted">
        {message}
      </span>
    </>
  )
}
