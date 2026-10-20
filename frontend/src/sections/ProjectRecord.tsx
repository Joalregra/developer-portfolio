import { Badge } from '../components/ui/Badge'
import { ChevronIcon, ChatIcon } from '../components/ui/icons'
import { RichText } from '../components/ui/RichText'
import type { Project } from '../data/projects'
import { useChatContext } from '../features/chat/ChatContext'
import { useLocale } from '../hooks/useLocale'
import { formatMonthRange } from '../lib/format'
import { ProjectDiagram } from './diagrams/ProjectDiagram'
import { ProjectDemo } from './ProjectDemo'

const subheading = 'heading text-lg'

/** One case study, readable in full without opening anything (PROJ-02). */
export function ProjectRecord({ project }: { project: Project }) {
  const { locale, t } = useLocale()
  const { openChat } = useChatContext()
  const titleId = `project-${project.id}`
  const hasDetail = project.stackMore.length > 0 || project.diagram

  return (
    <article
      id={`case-${project.id}`}
      aria-labelledby={titleId}
      className="record scroll-mt-20 grid gap-y-6 border-t border-line-strong py-10 first:border-t-0 first:pt-0 grid-cols-[minmax(0,1fr)] lg:grid-cols-[16rem_minmax(0,1fr)] lg:gap-x-12"
    >
      <div className="lg:col-start-2 lg:row-start-1">
        <h3 id={titleId} className="heading text-xl md:text-2xl">
          {project.name[locale]}
        </h3>
        <p className="measure mt-2 text-ink-muted">{project.tagline[locale]}</p>
      </div>

      <dl className="grid grid-cols-2 gap-x-4 gap-y-4 text-base sm:grid-cols-4 lg:sticky lg:top-24 lg:col-start-1 lg:row-span-2 lg:row-start-1 lg:grid-cols-1 lg:self-start">
        <div>
          <dt className="text-sm text-ink-muted">{t.projects.period}</dt>
          <dd className="font-semibold tabular-nums">
            {formatMonthRange(project.period.start, project.period.end, locale)}
          </dd>
        </div>
        <div>
          <dt className="text-sm text-ink-muted">{t.projects.teamLabel}</dt>
          <dd className="font-semibold">{t.projects.team(project.team)}</dd>
        </div>
        <div className="col-span-2 sm:col-span-4 lg:col-span-1">
          <dt className="text-sm text-ink-muted">{t.projects.role}</dt>
          <dd>{project.role[locale]}</dd>
        </div>
        <div className="col-span-2 sm:col-span-4 lg:col-span-1">
          <dt className="text-sm text-ink-muted">{t.projects.status}</dt>
          <dd className="mt-1 flex flex-wrap gap-2">
            <Badge>
              {project.status === 'nda' ? t.projects.statusNda : t.projects.statusProduction}
            </Badge>
          </dd>
        </div>
      </dl>

      <div className="space-y-6 lg:col-start-2 lg:row-start-2">
        <div>
          <h4 className={subheading}>{t.projects.problem}</h4>
          <p className="measure mt-2">{project.problem[locale]}</p>
        </div>

        <div>
          <h4 className={subheading}>{t.projects.did}</h4>
          <ul className="measure mt-2 list-disc space-y-2 pl-5 marker:text-accent">
            {project.did[locale].map((item) => (
              <li key={item}>
                <RichText text={item} />
              </li>
            ))}
          </ul>
        </div>

        <div>
          <h4 className={subheading}>{project.decision.title[locale]}</h4>
          <p className="measure mt-2">{project.decision.body[locale]}</p>
        </div>

        <div>
          <h4 className={subheading}>{t.projects.result}</h4>
          <p className="measure mt-2">
            <RichText text={project.result[locale]} />
          </p>
        </div>

        <div>
          <h4 className={subheading}>{t.projects.stack}</h4>
          <ul className="mt-2 flex flex-wrap gap-2">
            {project.stack.map((item) => (
              <li key={item}>
                <Badge>{item}</Badge>
              </li>
            ))}
          </ul>
        </div>

        {project.status === 'nda' && (
          <p className="measure border-l-2 border-accent pl-4 text-ink-muted">
            {project.runsInPrivateProduction ? t.projects.ndaNoteProduction : t.projects.ndaNote}
          </p>
        )}
        {project.demo && (
          <ProjectDemo demo={project.demo} headingClassName={subheading} titleId={titleId} />
        )}

        {hasDetail && (
          <details className="group">
            <summary className="flex min-h-11 w-fit cursor-pointer list-none items-center gap-2 font-semibold text-accent [&::-webkit-details-marker]:hidden">
              {t.projects.detail}
              <ChevronIcon
                size={18}
                className="transition-transform duration-(--dur-base) group-open:rotate-180"
              />
            </summary>
            <div className="mt-4 space-y-6">
              {project.stackMore.length > 0 && (
                <div>
                  <h4 className={subheading}>{t.projects.detailStack}</h4>
                  <ul className="mt-2 flex flex-wrap gap-2">
                    {project.stackMore.map((item) => (
                      <li key={item}>
                        <Badge>{item}</Badge>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {project.diagram && (
                <div>
                  <h4 className={subheading}>{t.projects.diagram}</h4>
                  <p className="mt-1 mb-3 text-sm text-ink-muted">{t.projects.diagramNote}</p>
                  <ProjectDiagram projectId={project.id} />
                </div>
              )}
            </div>
          </details>
        )}

        <button
          type="button"
          onClick={() => openChat(project.question[locale])}
          className="inline-flex min-h-11 items-center gap-2 rounded-md font-semibold text-accent underline underline-offset-4 hover:brightness-110"
        >
          <ChatIcon size={18} />
          {t.projects.ask}
        </button>
      </div>
    </article>
  )
}
