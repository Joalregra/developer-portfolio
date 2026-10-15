import { Section } from '../components/ui/Section'
import { projects } from '../data/projects'
import { skillGroups } from '../data/profileSections'
import { useLocale } from '../hooks/useLocale'

export function Skills() {
  const { locale, t } = useLocale()

  return (
    <Section id="skills" title={t.skills.title} intro={t.skills.intro}>
      <div className="space-y-10">
        {skillGroups.map((group) => (
          <div
            key={group.id}
            className="grid gap-3 grid-cols-[minmax(0,1fr)] lg:grid-cols-[16rem_minmax(0,1fr)] lg:gap-x-12"
          >
            <h3 className="heading text-lg">{t.skills.groups[group.id]}</h3>
            <ul className="grid gap-x-8 gap-y-3 sm:grid-cols-2">
              {group.skills.map((skill) => (
                <li key={skill.name} className="flex flex-wrap items-baseline gap-x-2">
                  <span className="font-semibold">{skill.name}</span>
                  {skill.usedIn && (
                    <span className="text-sm text-ink-muted">
                      {t.skills.usedIn}{' '}
                      {skill.usedIn.map((id, index) => {
                        const project = projects.find((item) => item.id === id)
                        return (
                          <span key={id}>
                            {index > 0 && ', '}
                            <a
                              href={`#case-${id}`}
                              className="underline underline-offset-2 hover:text-accent"
                            >
                              {project?.shortName[locale] ?? id}
                            </a>
                          </span>
                        )
                      })}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </Section>
  )
}
