import { MoonIcon, SunIcon } from '../ui/icons'
import { useLocale } from '../../hooks/useLocale'
import { useTheme } from '../../hooks/useTheme'
import { cx } from '../../lib/cx'

export function ThemeToggle({ className }: { className?: string }) {
  const { t } = useLocale()
  const { theme, toggle } = useTheme()
  const isDark = theme === 'dark'

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={isDark ? t.theme.toLight : t.theme.toDark}
      className={cx(
        'inline-flex size-11 items-center justify-center rounded-md border border-line-strong text-ink-muted transition-colors duration-(--dur-fast) hover:border-accent hover:text-accent',
        className,
      )}
    >
      {isDark ? <SunIcon /> : <MoonIcon />}
    </button>
  )
}
