import { profile, type Locale } from '../data/profile'

const labels: Record<Locale, { cv: string; contact: string }> = {
  es: { cv: 'Descargar CV', contact: 'Contactar' },
  en: { cv: 'Download CV', contact: 'Contact' },
}

interface HeroProps {
  locale?: Locale
}

export function Hero({ locale = 'es' }: HeroProps) {
  const text = labels[locale]

  return (
    <section aria-labelledby="hero-title" className="mx-auto max-w-3xl px-4 py-24">
      <p className="font-mono text-sm text-sky-400">{profile.location[locale]}</p>
      <h1 id="hero-title" className="mt-3 text-4xl font-bold text-slate-100 sm:text-5xl">
        {profile.name}
      </h1>
      <p className="mt-4 text-lg text-slate-300">{profile.role[locale]}</p>

      <div className="mt-8 flex flex-wrap gap-3">
        <a
          href={profile.links.cv}
          download
          className="rounded-lg bg-sky-500 px-4 py-2 font-medium text-slate-950 hover:bg-sky-400"
        >
          {text.cv}
        </a>
        <a
          href={`mailto:${profile.email}`}
          className="rounded-lg border border-slate-600 px-4 py-2 text-slate-100 hover:border-sky-400"
        >
          {text.contact}
        </a>
        <a
          href={profile.links.linkedin}
          target="_blank"
          rel="noreferrer"
          className="px-2 py-2 text-slate-300 hover:text-sky-400"
        >
          LinkedIn
        </a>
        <a
          href={profile.links.github}
          target="_blank"
          rel="noreferrer"
          className="px-2 py-2 text-slate-300 hover:text-sky-400"
        >
          GitHub
        </a>
      </div>
    </section>
  )
}
