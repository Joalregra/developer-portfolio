import { useLocale } from '../../hooks/useLocale'
import type { ProjectId } from '../../data/projects'
import { FlowDiagram } from './FlowDiagram'

export function ProjectDiagram({ projectId }: { projectId: ProjectId }) {
  const { t } = useLocale()

  if (projectId === 'reports') {
    const d = t.diagrams.reports
    return (
      <FlowDiagram
        title={d.title}
        desc={d.desc}
        layers={[
          [d.sources],
          [d.pipeline],
          [d.router, d.providers],
          [d.store, d.vectors],
          [d.search],
          [d.api],
          [d.ui],
        ]}
      />
    )
  }

  if (projectId === 'intel') {
    const d = t.diagrams.intel
    return (
      <FlowDiagram
        title={d.title}
        desc={d.desc}
        layers={[[d.sources], [d.ingest], [d.llm], [d.store], [d.api], [d.ui]]}
      />
    )
  }

  return null
}
