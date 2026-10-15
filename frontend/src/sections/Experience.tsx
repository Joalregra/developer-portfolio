import { RichText } from '../components/ui/RichText'
import { Section } from '../components/ui/Section'
import { experience } from '../data/profileSections'
import { projects } from '../data/projects'
import { useLocale } from '../hooks/useLocale'
import { formatMonthRange } from '../lib/format'

export function Experience() {
  const { locale, t } = useLocale()

  return (
    <Section id="experience" title={t.experience.title}>
      <ol className="space-y-12">
        {experience.map((entry) => (
          <li
            key={entry.id}
            className="grid gap-2 grid-cols-[minmax(0,1fr)] lg:grid-cols-[16rem_minmax(0,1fr)] lg:gap-x-12"
          >
            <p className="font-semibold tabular-nums text-ink-muted">
              {formatMonthRange(entry.period.start, entry.period.end, locale)}
            </p>
            <div>
              <h3 className="heading text-xl">{entry.role[locale]}</h3>
              <p className="mt-1 text-ink-muted">
                {entry.organization}
                {entry.city ? `, ${entry.city}` : ''}
              </p>
              <ul className="measure mt-4 list-disc space-y-2 pl-5 marker:text-accent">
                {entry.bullets[locale].map((bullet) => (
                  <li key={bullet}>
                    <RichText text={bullet} />
                  </li>
                ))}
              </ul>
              <p className="mt-3 flex flex-wrap gap-x-4">
                {entry.projectIds.map((id) => {
                  const project = projects.find((item) => item.id === id)
                  return project ? (
                    <a
                      key={id}
                      href={`#case-${id}`}
                      className="inline-flex min-h-11 items-center font-semibold text-accent underline underline-offset-4"
                    >
                      {t.experience.seeProject}: {project.shortName[locale]}
                    </a>
                  ) : null
                })}
              </p>
            </div>
          </li>
        ))}
      </ol>
    </Section>
  )
}
