import { Button } from '../components/ui/Button'
import { CopyEmailButton } from '../components/ui/CopyEmailButton'
import { ExternalLink } from '../components/ui/ExternalLink'
import { Section } from '../components/ui/Section'
import { DownloadIcon, GithubIcon, LinkedinIcon, MailIcon } from '../components/ui/icons'
import { profile } from '../data/profile'
import { useLocale } from '../hooks/useLocale'

export function Contact() {
  const { locale, t } = useLocale()
  const cv = profile.cv[locale]

  return (
    <Section id="contact" title={t.contact.title}>
      <div className="grid gap-6 grid-cols-[minmax(0,1fr)] lg:grid-cols-[16rem_minmax(0,1fr)] lg:gap-x-12">
        <div className="lg:col-start-2">
          <p className="measure text-lg">{t.contact.next}</p>
          <p className="mt-4 text-ink-muted">{t.contact.email}</p>
          <p className="text-xl font-bold break-all">
            <a
              className="underline underline-offset-4 hover:text-accent"
              href={`mailto:${profile.email}`}
            >
              {profile.email}
            </a>
          </p>
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <Button variant="primary" href={`mailto:${profile.email}`}>
              <MailIcon />
              {t.hero.contact}
            </Button>
            <CopyEmailButton email={profile.email} />
          </div>
          <div className="mt-6 flex flex-wrap items-center gap-2">
            <Button variant="secondary" href={cv.href} download>
              <DownloadIcon />
              {t.hero.cv}
              <span className="font-normal text-ink-muted">({t.hero.cvMeta(cv.pages)})</span>
            </Button>
            <ExternalLink href={profile.links.linkedin} icon={<LinkedinIcon size={18} />}>
              {t.hero.linkedin}
            </ExternalLink>
            <ExternalLink href={profile.links.github} icon={<GithubIcon size={18} />}>
              {t.hero.github}
            </ExternalLink>
          </div>
        </div>
      </div>
    </Section>
  )
}
