import { profile } from '../../data/profile'
import { useLocale } from '../../hooks/useLocale'
import { formatLongMonth } from '../../lib/format'
import { ExternalLink } from '../ui/ExternalLink'
import { containerClass } from '../ui/Section'
import { GithubIcon, LinkedinIcon, MailIcon } from '../ui/icons'

export function Footer() {
  const { locale, t } = useLocale()

  return (
    <footer className="border-t border-line py-10">
      <div
        className={`${containerClass} flex flex-col gap-6 md:flex-row md:items-start md:justify-between`}
      >
        <div className="measure space-y-1 text-ink-muted">
          <p className="font-semibold text-ink">{profile.name}</p>
          <p>{t.footer.updated(formatLongMonth(__BUILD_DATE__, locale))}</p>
          <p>{t.footer.stack}</p>
          <ExternalLink href={profile.links.repo} className="-ml-2">
            {t.footer.source}
          </ExternalLink>
        </div>
        <nav aria-label={t.footer.links}>
          <ul className="flex flex-wrap gap-x-2 gap-y-1">
            <li>
              <a
                href={`mailto:${profile.email}`}
                className="inline-flex min-h-11 items-center gap-2 rounded-md px-2 font-medium text-ink-muted hover:text-accent"
              >
                <MailIcon size={18} />
                {profile.email}
              </a>
            </li>
            <li>
              <ExternalLink href={profile.links.linkedin} icon={<LinkedinIcon size={18} />}>
                {t.hero.linkedin}
              </ExternalLink>
            </li>
            <li>
              <ExternalLink href={profile.links.github} icon={<GithubIcon size={18} />}>
                {t.hero.github}
              </ExternalLink>
            </li>
            <li>
              <a
                href={profile.cv[locale].href}
                download
                className="inline-flex min-h-11 items-center rounded-md px-2 font-medium text-ink-muted hover:text-accent"
              >
                {t.hero.cv}
              </a>
            </li>
          </ul>
        </nav>
      </div>
    </footer>
  )
}
