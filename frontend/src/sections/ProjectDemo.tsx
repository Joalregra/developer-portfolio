import { useEffect, useRef, useState } from 'react'
import { ExternalIcon, ZoomIcon } from '../components/ui/icons'
import { Lightbox } from '../components/ui/Lightbox'
import type { ProjectDemo as ProjectDemoData } from '../data/projects'
import { useLocale } from '../hooks/useLocale'

interface ProjectDemoProps {
  demo: ProjectDemoData
  headingClassName: string
  titleId: string
}

/** The public demo of a project: what it is, how to get in, and the screens it shows. */
export function ProjectDemo({ demo, headingClassName, titleId }: ProjectDemoProps) {
  const { locale, t } = useLocale()
  const headingId = `${titleId}-demo`
  const [active, setActive] = useState<number | null>(null)
  const triggers = useRef<Array<HTMLButtonElement | null>>([])
  const lastShown = useRef<number | null>(null)

  function show(index: number) {
    lastShown.current = index
    setActive(index)
  }

  // Closing the enlarged view puts the focus back on the thumbnail that was last shown.
  useEffect(() => {
    if (active === null && lastShown.current !== null) {
      triggers.current[lastShown.current]?.focus()
      lastShown.current = null
    }
  }, [active])

  const images = demo.screenshots.map((shot) => ({
    src: shot.src,
    width: shot.width,
    height: shot.height,
    alt: shot.alt[locale],
    caption: shot.caption[locale],
  }))

  return (
    <section aria-labelledby={headingId}>
      <h4 id={headingId} className={headingClassName}>
        {t.projects.demo}
      </h4>
      <p className="measure mt-2">{t.projects.demoIntro}</p>
      <a
        href={demo.url}
        target="_blank"
        rel="noopener noreferrer"
        className="mt-2 inline-flex min-h-11 items-center gap-2 rounded-md font-semibold text-accent underline underline-offset-4 hover:brightness-110"
      >
        {t.projects.demoLink}
        <ExternalIcon size={16} />
        <span className="sr-only"> {t.external}</span>
      </a>
      <ul className="mt-4 grid gap-6 sm:grid-cols-2">
        {images.map((image, index) => (
          <li key={image.src}>
            <figure>
              <button
                type="button"
                ref={(node) => {
                  triggers.current[index] = node
                }}
                onClick={() => show(index)}
                aria-haspopup="dialog"
                aria-label={t.projects.zoom(image.alt)}
                className="group relative block w-full cursor-zoom-in overflow-hidden rounded-md"
              >
                <img
                  src={image.src}
                  width={image.width}
                  height={image.height}
                  alt={image.alt}
                  loading="lazy"
                  decoding="async"
                  className="h-auto w-full rounded-md border border-line-strong"
                />
                <span
                  aria-hidden="true"
                  className="absolute right-2 bottom-2 inline-flex size-9 items-center justify-center rounded-md bg-paper text-ink opacity-90 shadow-panel transition-opacity duration-(--dur-fast) group-hover:opacity-100"
                >
                  <ZoomIcon size={18} />
                </span>
              </button>
              <figcaption className="mt-2 text-sm text-ink-muted">{image.caption}</figcaption>
            </figure>
          </li>
        ))}
      </ul>
      {active !== null && (
        <Lightbox images={images} index={active} onChange={show} onClose={() => setActive(null)} />
      )}
    </section>
  )
}
