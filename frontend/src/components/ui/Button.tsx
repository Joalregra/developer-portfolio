import type { AnchorHTMLAttributes, ButtonHTMLAttributes, ReactNode } from 'react'
import { cx } from '../../lib/cx'

type Variant = 'primary' | 'secondary' | 'quiet'

const base =
  'inline-flex min-h-11 items-center justify-center gap-2 rounded-md px-4 py-2 text-base font-semibold transition-colors duration-(--dur-fast) disabled:cursor-not-allowed disabled:opacity-50'

const variants: Record<Variant, string> = {
  primary: 'bg-accent text-accent-ink hover:brightness-110 active:brightness-95',
  secondary:
    'border border-line-strong bg-transparent text-ink hover:border-accent hover:text-accent',
  quiet: 'px-2 text-ink-muted hover:text-accent',
}

interface CommonProps {
  variant?: Variant
  className?: string
  children: ReactNode
}

type LinkProps = CommonProps & AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }
type ActionProps = CommonProps & ButtonHTMLAttributes<HTMLButtonElement> & { href?: undefined }

/** A link when it navigates or downloads, a button when it runs an action (A11Y-05). */
export function Button(props: LinkProps | ActionProps) {
  const { variant = 'secondary', className, children, ...rest } = props
  const classes = cx(base, variants[variant], className)

  if ('href' in rest && rest.href !== undefined) {
    return (
      <a className={classes} {...(rest as AnchorHTMLAttributes<HTMLAnchorElement>)}>
        {children}
      </a>
    )
  }
  return (
    <button
      type="button"
      className={classes}
      {...(rest as ButtonHTMLAttributes<HTMLButtonElement>)}
    >
      {children}
    </button>
  )
}
