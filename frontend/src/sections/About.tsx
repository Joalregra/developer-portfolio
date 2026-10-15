import { Section } from '../components/ui/Section'
import { useLocale } from '../hooks/useLocale'

export function About() {
  const { t } = useLocale()

  return (
    <Section id="about" title={t.about.title}>
      <div className="grid gap-10 grid-cols-[minmax(0,1fr)] lg:grid-cols-[16rem_minmax(0,1fr)] lg:gap-x-12">
        <div className="measure space-y-4 lg:col-start-2">
          {t.about.paragraphs.map((paragraph) => (
            <p key={paragraph}>{paragraph}</p>
          ))}
        </div>
        <div className="border-l-2 border-accent pl-4 lg:col-start-2">
          <h3 className="heading text-lg">{t.about.aiTitle}</h3>
          <p className="measure mt-2">{t.about.ai}</p>
        </div>
      </div>
    </Section>
  )
}
