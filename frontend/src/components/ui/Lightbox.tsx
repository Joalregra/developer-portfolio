import { useEffect, useRef, type MouseEvent } from 'react'
import { createPortal } from 'react-dom'
import { useFocusTrap } from '../../hooks/useFocusTrap'
import { useLocale } from '../../hooks/useLocale'
import { ChevronIcon, CloseIcon } from './icons'

export interface LightboxImage {
  src: string
  width: number
  height: number
  alt: string
  caption: string
}

interface LightboxProps {
  images: LightboxImage[]
  index: number
  onChange: (index: number) => void
  onClose: () => void
}

const navButton =
  'inline-flex size-11 shrink-0 items-center justify-center rounded-md bg-paper text-ink hover:text-accent'

/** Modal view of one image from a small gallery. Escape closes, the arrow keys move. */
export function Lightbox({ images, index, onChange, onClose }: LightboxProps) {
  const { t } = useLocale()
  const rootRef = useRef<HTMLDivElement>(null)
  const closeRef = useRef<HTMLButtonElement>(null)
  const image = images[index]
  const total = images.length

  useFocusTrap(rootRef, true)

  useEffect(() => {
    closeRef.current?.focus()
  }, [])

  // The page behind must not scroll while the image is open.
  useEffect(() => {
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = previous
    }
  }, [])

  // On the document, so the keys still work when focus was lost inside the dialog.
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose()
      else if (event.key === 'ArrowLeft') onChange((index - 1 + total) % total)
      else if (event.key === 'ArrowRight') onChange((index + 1) % total)
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [index, total, onChange, onClose])

  // A click on the dark area closes it; a click on the image or a button does not.
  function closeOnBackdrop(event: MouseEvent) {
    if (event.target === event.currentTarget) onClose()
  }

  return createPortal(
    <div
      ref={rootRef}
      role="dialog"
      aria-modal="true"
      aria-label={t.projects.lightbox.label}
      data-print="hide"
      onClick={closeOnBackdrop}
      className="fixed inset-0 z-50 flex flex-col bg-black/85 p-4 sm:p-6"
    >
      <div className="flex shrink-0 justify-end pb-3" onClick={closeOnBackdrop}>
        <button
          ref={closeRef}
          type="button"
          onClick={onClose}
          aria-label={t.projects.lightbox.close}
          className={navButton}
        >
          <CloseIcon />
        </button>
      </div>

      <div className="flex min-h-0 flex-1 items-center justify-center" onClick={closeOnBackdrop}>
        <img
          key={image.src}
          src={image.src}
          width={image.width}
          height={image.height}
          alt={image.alt}
          decoding="async"
          className="h-auto max-h-[calc(100dvh-11rem)] w-auto max-w-full rounded-md bg-paper object-contain"
        />
      </div>

      <div
        className="flex shrink-0 items-center justify-between gap-3 pt-3"
        onClick={closeOnBackdrop}
      >
        <button
          type="button"
          onClick={() => onChange((index - 1 + total) % total)}
          aria-label={t.projects.lightbox.previous}
          className={navButton}
        >
          <ChevronIcon className="rotate-90" />
        </button>
        <p aria-live="polite" className="measure text-center text-sm text-white">
          <span className="font-semibold tabular-nums">
            {t.projects.lightbox.count(index + 1, total)}
          </span>
          {' · '}
          {image.caption}
        </p>
        <button
          type="button"
          onClick={() => onChange((index + 1) % total)}
          aria-label={t.projects.lightbox.next}
          className={navButton}
        >
          <ChevronIcon className="-rotate-90" />
        </button>
      </div>
    </div>,
    document.body,
  )
}
