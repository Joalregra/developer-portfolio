import { Fragment } from 'react'

const URL_PATTERN = /(https?:\/\/[^\s<>"']+[^\s<>"'.,;:!?)])/g

/** Plain text with detected links made clickable. Never renders HTML from the input. */
export function LinkedText({ text }: { text: string }) {
  const parts = text.split(URL_PATTERN)
  return (
    <>
      {parts.map((part, index) =>
        index % 2 === 1 ? (
          <a
            key={index}
            href={part}
            target="_blank"
            rel="noopener noreferrer"
            className="break-all underline underline-offset-2 hover:text-accent"
          >
            {part}
          </a>
        ) : (
          <Fragment key={index}>{part}</Fragment>
        ),
      )}
    </>
  )
}
