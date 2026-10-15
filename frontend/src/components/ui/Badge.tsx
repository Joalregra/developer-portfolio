import type { ReactNode } from 'react'

interface BadgeProps {
  children: ReactNode
}

/** Plain text label for stack items and states. No logos: the name is always the content. */
export function Badge({ children }: BadgeProps) {
  return (
    <span className="inline-flex items-center rounded-sm border border-line bg-surface px-2 py-0.5 text-sm font-medium text-ink">
      {children}
    </span>
  )
}
