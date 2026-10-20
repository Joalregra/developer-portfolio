import { useEffect, useRef, useState } from 'react'
import { NAV_SECTIONS } from '../../data/nav'
import { profile } from '../../data/profile'
import { useActiveSection } from '../../hooks/useActiveSection'
import { useLocale } from '../../hooks/useLocale'
import { containerClass } from '../ui/Section'
import { CloseIcon, MenuIcon } from '../ui/icons'
import { LanguageSwitch } from './LanguageSwitch'
import { ThemeToggle } from './ThemeToggle'

const MENU_ID = 'site-menu'

export function Header() {
  const { t } = useLocale()
  const [open, setOpen] = useState(false)
  const headerRef = useRef<HTMLElement>(null)
  const buttonRef = useRef<HTMLButtonElement>(null)
  const active = useActiveSection(NAV_SECTIONS)

  // Escape closes the menu and returns focus to its button; a tap outside closes it too (NAV-03).
  useEffect(() => {
    if (!open) return
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setOpen(false)
        buttonRef.current?.focus()
      }
    }
    function onPointerDown(event: PointerEvent) {
      if (headerRef.current && !headerRef.current.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('keydown', onKeyDown)
    document.addEventListener('pointerdown', onPointerDown)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      document.removeEventListener('pointerdown', onPointerDown)
    }
  }, [open])

  return (
    <header
      ref={headerRef}
      data-print="hide"
      className="sticky top-0 z-30 border-b border-line bg-paper"
    >
      <div className={`${containerClass} flex h-(--header-h) items-center justify-between gap-2`}>
        <a
          href="#top"
          className="display -mb-px inline-flex min-h-11 items-center text-lg whitespace-nowrap min-[360px]:text-xl"
        >
          {profile.shortName}
        </a>

        <nav aria-label={t.nav.label} className="lg:flex-1">
          <ul
            id={MENU_ID}
            className={`${
              open ? 'flex' : 'hidden'
            } absolute inset-x-0 top-(--header-h) flex-col gap-1 border-b border-line bg-paper px-4 py-3 shadow-panel sm:px-6 lg:static lg:flex lg:flex-row lg:justify-center lg:gap-1 lg:border-0 lg:p-0 lg:shadow-none`}
          >
            {NAV_SECTIONS.map((id) => {
              const isActive = active === id
              return (
                <li key={id}>
                  <a
                    href={`#${id}`}
                    aria-current={isActive ? 'location' : undefined}
                    onClick={() => setOpen(false)}
                    className={`relative flex min-h-11 items-center rounded-md px-3 font-medium transition-colors duration-(--dur-fast) hover:text-accent lg:after:absolute lg:after:inset-x-3 lg:after:bottom-1.5 lg:after:h-0.5 lg:after:origin-left lg:after:bg-accent lg:after:transition-transform lg:after:duration-(--dur-base) ${
                      isActive
                        ? 'font-bold text-ink lg:after:scale-x-100'
                        : 'text-ink-muted lg:after:scale-x-0'
                    }`}
                  >
                    {t.nav[id]}
                  </a>
                </li>
              )
            })}
            <li className="lg:hidden">
              <ThemeToggle />
            </li>
          </ul>
        </nav>

        <div className="flex items-center gap-2">
          <LanguageSwitch />
          <div className="hidden lg:block">
            <ThemeToggle />
          </div>
          <button
            ref={buttonRef}
            type="button"
            aria-expanded={open}
            aria-controls={MENU_ID}
            aria-label={open ? t.nav.closeMenu : t.nav.openMenu}
            onClick={() => setOpen((value) => !value)}
            className="inline-flex size-11 items-center justify-center rounded-md border border-line-strong text-ink lg:hidden"
          >
            {open ? <CloseIcon /> : <MenuIcon />}
          </button>
        </div>
      </div>
    </header>
  )
}
