import { useLocale } from '../../hooks/useLocale'
import { toQuickQuestionId } from '../../services/api'
import { useChatContext } from './ChatContext'

/** Chips from section 9 of the knowledge file. Open at the start, collapsible afterwards. */
export function QuickQuestions() {
  const { t } = useLocale()
  const { chat } = useChatContext()
  const started = chat.messages.length > 0

  const chips = (
    <ul className="flex flex-wrap gap-2">
      {t.quickQuestions.map((item) => (
        <li key={item.id}>
          <button
            type="button"
            aria-disabled={chat.sending}
            onClick={() => {
              chat.send(item.question, toQuickQuestionId(item.id))
              // The chips re-mount once the conversation starts, so keep the focus in the panel.
              document.getElementById('chat-input')?.focus()
            }}
            className="min-h-11 rounded-md border border-line-strong px-3 text-sm font-medium text-ink transition-colors duration-(--dur-fast) hover:border-accent hover:text-accent aria-disabled:opacity-50"
          >
            {item.label}
          </button>
        </li>
      ))}
    </ul>
  )

  if (!started) {
    return (
      <div className="px-4 pb-3">
        <p className="mb-2 text-sm text-ink-muted">{t.chat.quickLabel}</p>
        {chips}
      </div>
    )
  }

  return (
    <details className="px-4 pb-3">
      <summary className="flex min-h-11 cursor-pointer items-center text-sm font-medium text-ink-muted hover:text-accent">
        {t.chat.quickLabel}
      </summary>
      <div className="pt-1">{chips}</div>
    </details>
  )
}
