import type { ReactNode } from 'react'
import { cx } from '../../lib/cx'

interface SectionProps {
  id: string
  title: string
  intro?: string
  children: ReactNode
  className?: string
}

export const containerClass = 'mx-auto w-full max-w-[1200px] px-4 sm:px-6 lg:px-8'

/** A page section with its heading. The id is the same in both languages (IA-02). */
export function Section({ id, title, intro, children, className }: SectionProps) {
  const headingId = `${id}-title`
  return (
    <section id={id} aria-labelledby={headingId} className={cx('py-16 md:py-24', className)}>
      <div className={containerClass}>
        <h2 id={headingId} className="heading text-2xl md:text-3xl">
          {title}
        </h2>
        {intro && <p className="measure mt-3 text-ink-muted">{intro}</p>}
        <div className="mt-10 md:mt-12">{children}</div>
      </div>
    </section>
  )
}
