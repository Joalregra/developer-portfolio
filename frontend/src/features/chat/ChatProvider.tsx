import { Suspense, useCallback, useMemo, useRef, useState, type ReactNode } from 'react'
import { useLocale } from '../../hooks/useLocale'
import type { QuickQuestionId } from '../../services/api'
import { ChatContext } from './ChatContext'
import { ChatLauncher } from './ChatLauncher'
import { ChatPanel } from './lazy'
import { useChat } from './useChat'

export function ChatProvider({ children }: { children: ReactNode }) {
  const { locale } = useLocale()
  const chat = useChat(locale)
  const [isOpen, setIsOpen] = useState(false)
  const launcherRef = useRef<HTMLButtonElement | null>(null)
  const openerRef = useRef<HTMLElement | null>(null)
  const { send } = chat

  const openChat = useCallback(
    (question?: string, quick?: QuickQuestionId) => {
      // Remember what opened the panel so focus can go back to it (CHAT-01).
      const active = document.activeElement
      openerRef.current = active instanceof HTMLElement && active !== document.body ? active : null
      setIsOpen(true)
      if (question) send(question, quick)
    },
    [send],
  )

  const closeChat = useCallback(() => {
    setIsOpen(false)
    window.requestAnimationFrame(() => {
      const opener = openerRef.current
      // Back to the opener if it is still on the page and visible, otherwise to the launcher.
      const target =
        opener && opener.isConnected && opener.getClientRects().length > 0
          ? opener
          : launcherRef.current
      target?.focus()
    })
  }, [])

  const value = useMemo(
    () => ({ isOpen, openChat, closeChat, launcherRef, chat }),
    [isOpen, openChat, closeChat, chat],
  )

  return (
    <ChatContext.Provider value={value}>
      {children}
      <ChatLauncher />
      {isOpen && (
        <Suspense fallback={null}>
          <ChatPanel />
        </Suspense>
      )}
    </ChatContext.Provider>
  )
}
