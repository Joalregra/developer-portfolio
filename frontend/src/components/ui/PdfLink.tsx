import type { ReactNode } from 'react'
import { useLocale } from '../../hooks/useLocale'
import { FileIcon } from './icons'

interface PdfLinkProps {
  href: string
  kb: number
  children: ReactNode
}

/** Link to a PDF in /public. Opens in a new tab and says so, with the file size. */
export function PdfLink({ href, kb, children }: PdfLinkProps) {
  const { t } = useLocale()
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="mt-1 inline-flex min-h-11 items-center gap-2 font-semibold text-accent"
    >
      <FileIcon size={16} />
      <span className="underline underline-offset-4">{children}</span>
      <span className="font-normal text-ink-muted">(PDF, {kb} KB)</span>
      <span className="sr-only"> {t.external}</span>
    </a>
  )
}
