import { useEffect, useRef } from 'react'
import { LinkedText } from '../../components/ui/LinkedText'
import { useLocale } from '../../hooks/useLocale'
import { profile } from '../../data/profile'
import { useChatContext } from './ChatContext'

export function MessageList() {
  const { t } = useLocale()
  const { chat, closeChat } = useChatContext()
  const { messages, sending, error, retry } = chat
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView?.({ block: 'end' })
  }, [messages.length, sending, error])

  return (
    <div
      role="log"
      aria-live="polite"
      aria-label={t.chat.title}
      className="flex flex-1 flex-col gap-3 overflow-y-auto px-4 py-4"
    >
      <p className="measure text-ink-muted">{t.chat.greeting}</p>

      {messages.map((message) => {
        const fromUser = message.role === 'user'
        return (
          <div key={message.id} className={fromUser ? 'flex justify-end' : 'flex justify-start'}>
            <div
              className={
                fromUser
                  ? 'max-w-[85%] rounded-lg rounded-br-sm bg-accent px-3 py-2 text-accent-ink'
                  : 'max-w-[92%] rounded-lg rounded-bl-sm border border-line bg-surface px-3 py-2 text-ink'
              }
            >
              <span className="sr-only">{fromUser ? t.chat.you : t.chat.assistant} </span>
              <p className="whitespace-pre-wrap break-words">
                <LinkedText text={message.content} />
              </p>
              {message.section && (
                <p className="mt-2 text-sm text-ink-muted">
                  {t.chat.seeIn}{' '}
                  <a
                    href={`#${message.section}`}
                    onClick={closeChat}
                    className="font-medium underline underline-offset-2 hover:text-accent"
                  >
                    {t.chat.sections[message.section]}
                  </a>
                </p>
              )}
            </div>
          </div>
        )
      })}

      {sending && (
        <div className="flex justify-start" role="status">
          <span className="sr-only">{t.chat.typing}</span>
          <div
            aria-hidden="true"
            className="flex gap-1 rounded-lg rounded-bl-sm border border-line bg-surface px-3 py-3"
          >
            <span className="typing-dot size-2 rounded-full bg-ink-muted" />
            <span className="typing-dot size-2 rounded-full bg-ink-muted" />
            <span className="typing-dot size-2 rounded-full bg-ink-muted" />
          </div>
        </div>
      )}

      {error && (
        <div role="alert" className="rounded-md border border-line-strong bg-surface p-3 text-sm">
          {error === 'unavailable' && (
            <p>
              {t.chat.unavailable}{' '}
              <a
                className="font-medium underline underline-offset-2"
                href={`mailto:${profile.email}`}
              >
                {profile.email}
              </a>
              .
            </p>
          )}
          {error === 'rateLimit' && <p>{t.chat.rateLimit}</p>}
          {error === 'offline' && <p>{t.chat.offline}</p>}
          {error !== 'rateLimit' && (
            <button
              type="button"
              onClick={retry}
              className="mt-2 min-h-11 rounded-md border border-line-strong px-3 font-semibold hover:border-accent hover:text-accent"
            >
              {t.chat.retry}
            </button>
          )}
        </div>
      )}
      <div ref={endRef} />
    </div>
  )
}
