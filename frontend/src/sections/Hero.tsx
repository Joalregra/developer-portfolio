import { useState, type FormEvent } from 'react'
import { Button } from '../components/ui/Button'
import { ExternalLink } from '../components/ui/ExternalLink'
import { containerClass } from '../components/ui/Section'
import { DownloadIcon, GithubIcon, LinkedinIcon, MailIcon } from '../components/ui/icons'
import { profile } from '../data/profile'
import { useChatContext } from '../features/chat/ChatContext'
import { loadChatPanel } from '../features/chat/lazy'
import { useLocale } from '../hooks/useLocale'
import { toQuickQuestionId } from '../services/api'

const SUGGESTED = ['projects', 'stack', 'challenge']

export function Hero() {
  const { locale, t } = useLocale()
  const { openChat } = useChatContext()
  const [question, setQuestion] = useState('')
  const cv = profile.cv[locale]
  const suggestions = t.quickQuestions.filter((item) => SUGGESTED.includes(item.id))

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    const text = question.trim()
    setQuestion('')
    openChat(text || undefined)
  }

  return (
    <section id="top" aria-labelledby="hero-title" className="pt-4 pb-16 md:pt-14 md:pb-24">
      <div
        className={`${containerClass} grid gap-5 md:gap-8 grid-cols-[minmax(0,1fr)] lg:grid-cols-[minmax(0,1fr)_26rem] lg:gap-x-16 lg:gap-y-10`}
      >
        {/* Below lg the two parts are grid items, so the actions can move after the assistant on
            the narrowest phones; from lg on this is one block in the left column. */}
        <div className="contents lg:col-start-1 lg:row-start-1 lg:block">
          <div>
            <div className="flex items-center gap-4 md:gap-6">
              {/* Temporary photo; served at most at 2x the displayed size (HERO-05). */}
              <img
                src="/img/johan-240.webp"
                srcSet="/img/johan-144.webp 144w, /img/johan-240.webp 240w"
                sizes="(min-width: 768px) 120px, 60px"
                width={240}
                height={320}
                alt={t.hero.photoAlt}
                fetchPriority="high"
                className="h-20 w-15 shrink-0 rounded-md border border-line object-cover md:h-40 md:w-30"
              />
              <h1 id="hero-title" className="display text-[clamp(2.25rem,7vw,4.5rem)]">
                {profile.name}
              </h1>
            </div>
            <p className="mt-3 max-w-[36ch] text-base font-medium sm:text-lg md:mt-4 md:text-xl">
              {profile.role[locale]}
            </p>
            <div className="mt-3 space-y-1">
              <p className="text-ink-muted">{profile.location[locale]}</p>
              <p className="font-semibold text-accent">{profile.availability[locale]}</p>
            </div>
          </div>

          {/* Under 360 px the assistant field would sit below the fold, so the actions follow it. */}
          <div className="order-1 flex flex-wrap items-center gap-2 min-[360px]:order-0 md:-mt-2 lg:mt-6">
            <Button variant="primary" href={`mailto:${profile.email}`}>
              <MailIcon />
              {t.hero.contact}
            </Button>
            <Button variant="secondary" href={cv.href} download>
              <DownloadIcon />
              {t.hero.cv}
              <span className="hidden font-normal text-ink-muted sm:inline">
                ({t.hero.cvMeta(cv.pages)})
              </span>
            </Button>
            {/* On phones the file details sit under the buttons so both fit on one row. */}
            <p className="w-full text-sm text-ink-muted sm:hidden">
              {t.hero.cv}: {t.hero.cvMeta(cv.pages)}
            </p>
            <div className="flex items-center gap-1">
              <ExternalLink href={profile.links.linkedin} icon={<LinkedinIcon size={18} />}>
                {t.hero.linkedin}
              </ExternalLink>
              <ExternalLink href={profile.links.github} icon={<GithubIcon size={18} />}>
                {t.hero.github}
              </ExternalLink>
            </div>
          </div>
        </div>

        <aside
          id="consult"
          aria-labelledby="consult-title"
          data-print="hide"
          className="on-spot rounded-lg bg-spot p-4 text-on-spot sm:p-6 lg:col-start-2 lg:row-span-2 lg:row-start-1 lg:self-start"
        >
          <h2 id="consult-title" className="heading text-xl md:text-2xl">
            {t.hero.consultTitle}
          </h2>
          <form onSubmit={onSubmit} className="mt-3 sm:mt-4">
            <label htmlFor="hero-question" className="sr-only">
              {t.hero.consultLabel}
            </label>
            <div className="flex gap-2">
              <input
                id="hero-question"
                type="text"
                value={question}
                maxLength={1000}
                autoComplete="off"
                placeholder={t.hero.consultPlaceholder}
                onFocus={() => void loadChatPanel()}
                onChange={(event) => setQuestion(event.target.value)}
                className="min-h-11 min-w-0 flex-1 rounded-md border border-on-spot-muted bg-transparent px-3 text-on-spot placeholder:text-on-spot-muted"
              />
              <button
                type="submit"
                className="min-h-11 rounded-md bg-on-spot px-4 font-semibold text-spot transition-opacity duration-(--dur-fast) hover:opacity-90"
              >
                {t.hero.consultSend}
              </button>
            </div>
          </form>
          <div className="mt-4" role="group" aria-label={t.hero.suggestionsLabel}>
            <ul className="flex flex-wrap gap-2">
              {suggestions.map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    onClick={() => openChat(item.question, toQuickQuestionId(item.id))}
                    className="min-h-11 rounded-md border border-on-spot-muted px-3 text-sm font-medium text-on-spot transition-colors duration-(--dur-fast) hover:bg-on-spot hover:text-spot"
                  >
                    {item.label}
                  </button>
                </li>
              ))}
            </ul>
          </div>
          <p className="mt-4 text-sm text-on-spot-muted">{t.hero.notice}</p>
        </aside>

        <p className="measure order-2 text-lg min-[360px]:order-0 lg:col-start-1 lg:row-start-2">
          {profile.valueProp[locale]}
        </p>
      </div>
    </section>
  )
}
