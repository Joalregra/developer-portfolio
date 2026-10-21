import { useState, type FormEvent, type KeyboardEvent, type RefObject } from 'react'
import { SendIcon } from '../../components/ui/icons'
import { useLocale } from '../../hooks/useLocale'
import { useChatContext } from './ChatContext'
import { COUNTER_FROM, MAX_LENGTH } from './useChat'

export function Composer({ inputRef }: { inputRef: RefObject<HTMLTextAreaElement | null> }) {
  const { t } = useLocale()
  const { chat } = useChatContext()
  const [value, setValue] = useState('')

  const length = value.length
  const tooLong = length > MAX_LENGTH
  const canSend = value.trim().length > 0 && !tooLong && !chat.sending

  function submit() {
    if (!canSend) return
    if (chat.send(value)) setValue('')
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    submit()
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    // Enter sends, Shift+Enter adds a line break (CHAT-02). Ignore Enter while composing text (IME).
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      submit()
    }
  }

  return (
    <form onSubmit={onSubmit} className="shrink-0 border-t border-line px-4 pt-3 pb-2">
      <label htmlFor="chat-input" className="sr-only">
        {t.chat.inputLabel}
      </label>
      <div className="flex items-end gap-2">
        <textarea
          id="chat-input"
          ref={inputRef}
          rows={1}
          value={value}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={onKeyDown}
          placeholder={t.chat.placeholder}
          aria-invalid={tooLong}
          aria-describedby="chat-counter"
          className="max-h-32 min-h-11 flex-1 resize-none rounded-md [field-sizing:content] border border-line-strong bg-paper px-3 py-2 text-ink placeholder:text-ink-muted"
        />
        <button
          type="submit"
          disabled={!canSend}
          className="inline-flex min-h-11 items-center gap-2 rounded-md bg-accent px-4 font-semibold text-accent-ink transition-colors duration-(--dur-fast) hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <SendIcon size={18} />
          {t.chat.send}
        </button>
      </div>
      <p
        id="chat-counter"
        className={`mt-1 text-sm empty:hidden ${tooLong ? 'font-semibold text-danger' : 'text-ink-muted'}`}
      >
        {length >= COUNTER_FROM ? t.chat.counter(length, MAX_LENGTH) : ''}
      </p>
      <p className="mt-2 text-xs leading-snug text-ink-muted">
        <span>{t.chat.notice}</span> <span>{t.chat.privacy}</span>
      </p>
    </form>
  )
}
