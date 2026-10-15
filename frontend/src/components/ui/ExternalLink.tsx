import type { ReactNode } from 'react'
import { useLocale } from '../../hooks/useLocale'
import { cx } from '../../lib/cx'
import { ExternalIcon } from './icons'

interface ExternalLinkProps {
  href: string
  children: ReactNode
  icon?: ReactNode
  className?: string
}

/** Opens in a new tab and says so, for sighted and screen reader users (ICO-03). */
export function ExternalLink({ href, children, icon, className }: ExternalLinkProps) {
  const { t } = useLocale()
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className={cx(
        'inline-flex min-h-11 items-center gap-2 rounded-md px-2 font-medium text-ink-muted transition-colors duration-(--dur-fast) hover:text-accent',
        className,
      )}
    >
      {icon}
      <span>{children}</span>
      <ExternalIcon size={14} />
      <span className="sr-only"> {t.external}</span>
    </a>
  )
}
