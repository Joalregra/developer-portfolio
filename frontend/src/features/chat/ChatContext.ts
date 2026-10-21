import { createContext, useContext, type RefObject } from 'react'
import type { QuickQuestionId } from '../../services/api'
import type { ChatState } from './useChat'

export interface ChatContextValue {
  isOpen: boolean
  /** Opens the panel; with a question it also sends it right away. */
  openChat: (question?: string, quick?: QuickQuestionId) => void
  closeChat: () => void
  launcherRef: RefObject<HTMLButtonElement | null>
  chat: ChatState
}

export const ChatContext = createContext<ChatContextValue | null>(null)

export function useChatContext(): ChatContextValue {
  const value = useContext(ChatContext)
  if (!value) throw new Error('useChatContext must be used inside <ChatProvider>')
  return value
}
