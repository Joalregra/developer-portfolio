import { locales, type Locale } from '../../data/profile'
import { useLocale } from '../../hooks/useLocale'

/** Text, not flags: a flag is a country, not a language (I18N-03). */
export function LanguageSwitch() {
  const { locale, setLocale, t } = useLocale()

  return (
    <div role="group" aria-label={t.language.label} className="flex items-center gap-2">
      {locales.map((code: Locale) => {
        const selected = code === locale
        return (
          <button
            key={code}
            type="button"
            lang={code}
            aria-pressed={selected}
            aria-label={`${code.toUpperCase()}, ${t.language[code]}`}
            onClick={() => setLocale(code)}
            className={`inline-flex size-11 items-center justify-center rounded-md text-sm font-bold transition-colors duration-(--dur-fast) ${
              selected
                ? 'bg-ink text-paper'
                : 'border border-line-strong text-ink-muted hover:border-accent hover:text-accent'
            }`}
          >
            {code.toUpperCase()}
          </button>
        )
      })}
    </div>
  )
}
