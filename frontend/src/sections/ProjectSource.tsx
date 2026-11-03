import { ExternalIcon } from '../components/ui/icons'
import type { ProjectSource as ProjectSourceData } from '../data/projects'
import { useLocale } from '../hooks/useLocale'

interface ProjectSourceProps {
  source: ProjectSourceData
  headingClassName: string
  titleId: string
}

const linkClass =
  'inline-flex min-h-11 items-center gap-2 rounded-md font-semibold text-accent underline underline-offset-4 hover:brightness-110'

/** Where to read the code and the documentation of a project, and where the code was developed. */
export function ProjectSource({ source, headingClassName, titleId }: ProjectSourceProps) {
  const { t } = useLocale()
  const headingId = `${titleId}-source`
  const links = [
    { href: source.url, label: t.projects.sourceLink },
    { href: source.docsUrl, label: t.projects.docsLink },
    { href: source.upstreamUrl, label: t.projects.upstreamLink },
  ]

  return (
    <section aria-labelledby={headingId}>
      <h4 id={headingId} className={headingClassName}>
        {t.projects.source}
      </h4>
      <p className="measure mt-2">{t.projects.sourceIntro}</p>
      <ul className="mt-2 flex flex-col gap-x-6 sm:flex-row sm:flex-wrap">
        {links.map((link) => (
          <li key={link.href}>
            <a href={link.href} target="_blank" rel="noopener noreferrer" className={linkClass}>
              {link.label}
              <ExternalIcon size={16} />
              <span className="sr-only"> {t.external}</span>
            </a>
          </li>
        ))}
      </ul>
    </section>
  )
}
