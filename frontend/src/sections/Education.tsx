import { ExternalLink } from '../components/ui/ExternalLink'
import { FileIcon } from '../components/ui/icons'
import { Section } from '../components/ui/Section'
import { certifications, education } from '../data/profileSections'
import { useLocale } from '../hooks/useLocale'
import { formatMonth, formatMonthRange } from '../lib/format'

export function Education() {
  const { locale, t } = useLocale()

  return (
    <Section id="education" title={t.education.title}>
      <div className="space-y-12">
        <div className="grid gap-2 grid-cols-[minmax(0,1fr)] lg:grid-cols-[16rem_minmax(0,1fr)] lg:gap-x-12">
          <p className="font-semibold tabular-nums text-ink-muted">
            {formatMonthRange(education.period.start, education.period.end, locale)}
          </p>
          <div>
            <h3 className="heading text-xl">{education.degree[locale]}</h3>
            <p className="mt-1 text-ink-muted">{education.school}</p>
            <p className="measure mt-3">{education.note[locale]}</p>
          </div>
        </div>

        <div className="grid gap-3 grid-cols-[minmax(0,1fr)] lg:grid-cols-[16rem_minmax(0,1fr)] lg:gap-x-12">
          <h3 className="heading text-lg">{t.education.certifications}</h3>
          <ul className="grid gap-x-8 gap-y-5 sm:grid-cols-2">
            {certifications.map((certification) => (
              <li key={certification.id} className="border-l-2 border-line pl-4">
                <p className="font-semibold">{certification.name}</p>
                <p className="text-ink-muted">
                  {certification.issuer}
                  {certification.date ? `, ${formatMonth(certification.date, locale)}` : ''}
                </p>
                {certification.detail && (
                  <p className="tabular-nums">{certification.detail[locale]}</p>
                )}
                {certification.pdf && (
                  <a
                    href={certification.pdf.href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-1 inline-flex min-h-11 items-center gap-2 font-semibold text-accent"
                  >
                    <FileIcon size={16} />
                    <span className="underline underline-offset-4">{t.education.viewPdf}</span>
                    <span className="font-normal text-ink-muted">
                      (PDF, {certification.pdf.kb} KB)
                    </span>
                    <span className="sr-only"> {t.external}</span>
                  </a>
                )}
                {certification.verifyUrl && (
                  <ExternalLink href={certification.verifyUrl} className="-ml-2">
                    {t.education.verify}
                  </ExternalLink>
                )}
              </li>
            ))}
          </ul>
        </div>

        <div className="grid gap-3 grid-cols-[minmax(0,1fr)] lg:grid-cols-[16rem_minmax(0,1fr)] lg:gap-x-12">
          <h3 className="heading text-lg">{t.education.languages}</h3>
          <p className="measure">{education.languages[locale]}</p>
        </div>
      </div>
    </Section>
  )
}
