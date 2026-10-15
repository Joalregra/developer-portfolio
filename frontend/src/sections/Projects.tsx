import { Section } from '../components/ui/Section'
import { projects } from '../data/projects'
import { useLocale } from '../hooks/useLocale'
import { ProjectRecord } from './ProjectRecord'

export function Projects() {
  const { t } = useLocale()

  return (
    <Section id="projects" title={t.projects.title} intro={t.projects.intro}>
      {projects.map((project) => (
        <ProjectRecord key={project.id} project={project} />
      ))}
    </Section>
  )
}
