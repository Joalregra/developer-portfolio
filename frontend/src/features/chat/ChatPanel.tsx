import { useEffect, useRef } from 'react'
import { CloseIcon, ResetIcon } from '../../components/ui/icons'
import { useFocusTrap } from '../../hooks/useFocusTrap'
import { useLocale } from '../../hooks/useLocale'
import { useMediaQuery } from '../../hooks/useMediaQuery'
import { useChatContext } from './ChatContext'
import { Composer } from './Composer'
import { PANEL_ID } from './ChatLauncher'
import { MessageList } from './MessageList'
import { QuickQuestions } from './QuickQuestions'

/**
 * Desktop: a non-modal panel anchored to the launcher. Phones (under 640 px): a full-screen
 * modal dialog with trapped focus (CHAT-01).
 */
export default function ChatPanel() {
  const { t } = useLocale()
  const { closeChat, chat } = useChatContext()
  const panelRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const isPhone = useMediaQuery('(max-width: 639px)')

  useFocusTrap(panelRef, isPhone)

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  // On the document, so Escape still closes the panel when focus was lost inside it (CHAT-02).
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') closeChat()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [closeChat])

  return (
    <div
      id={PANEL_ID}
      ref={panelRef}
      role="dialog"
      aria-modal={isPhone}
      aria-labelledby="chat-title"
      data-print="hide"
      className="chat-panel fixed inset-0 z-50 flex flex-col overflow-hidden bg-paper sm:inset-auto sm:right-6 sm:bottom-24 sm:h-[min(42rem,calc(100dvh-7.5rem))] sm:w-[25rem] sm:rounded-lg sm:border sm:border-line-strong sm:shadow-panel"
    >
      <header className="flex shrink-0 items-center justify-between gap-2 border-b border-line px-4 py-1">
        <h2 id="chat-title" className="heading text-lg whitespace-nowrap">
          {t.chat.title}
        </h2>
        <div className="flex items-center gap-1">
          {chat.messages.length > 0 && (
            <button
              type="button"
              onClick={chat.reset}
              className="inline-flex min-h-11 items-center gap-2 rounded-md px-2 text-sm font-medium whitespace-nowrap text-ink-muted hover:text-accent"
            >
              <ResetIcon size={16} />
              {t.chat.newConversation}
            </button>
          )}
          <button
            type="button"
            onClick={closeChat}
            aria-label={t.chat.close}
            className="inline-flex size-11 items-center justify-center rounded-md text-ink-muted hover:text-accent"
          >
            <CloseIcon />
          </button>
        </div>
      </header>
      <MessageList />
      {chat.messages.length > 0 && <QuickQuestions />}
      <Composer inputRef={inputRef} />
    </div>
  )
}
