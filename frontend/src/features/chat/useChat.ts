import { useCallback, useEffect, useRef, useState } from 'react'
import type { Locale } from '../../data/profile'
import { readStorage, removeStorage, writeStorage } from '../../lib/storage'
import {
  ApiError,
  postChat,
  postFeedback,
  type ChatSection,
  type QuickQuestionId,
} from '../../services/api'

export const MAX_LENGTH = 1000
export const COUNTER_FROM = 800
const STORAGE_KEY = 'chat:v1'
// The backend accepts 6 earlier messages and rejects more with a 422.
const HISTORY_LIMIT = 6

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  /** Answers only: the section of the page the answer is based on. */
  section?: ChatSection
  /** Questions only: set when the text came from a quick-question button. */
  quick?: QuickQuestionId
  /** Answers only: the id the backend gave it, needed to rate it. */
  messageId?: string
  /** Answers only: how the visitor rated it. One rating per answer. */
  rating?: 'up' | 'down'
}

export type ChatError = 'unavailable' | 'rateLimit' | 'offline'

function restore(): ChatMessage[] {
  const raw = readStorage('session', STORAGE_KEY)
  if (!raw) return []
  try {
    const parsed: unknown = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed
      .filter(
        (item): item is ChatMessage =>
          typeof item === 'object' &&
          item !== null &&
          typeof item.id === 'string' &&
          (item.role === 'user' || item.role === 'assistant') &&
          typeof item.content === 'string',
      )
      .map((item) => ({
        ...item,
        // Stored by the browser, so it is checked like any other input.
        messageId: typeof item.messageId === 'string' ? item.messageId : undefined,
        rating: item.rating === 'up' || item.rating === 'down' ? item.rating : undefined,
      }))
  } catch {
    return []
  }
}

function classify(error: unknown): ChatError {
  if (error instanceof ApiError && error.status === 429) return 'rateLimit'
  if (typeof navigator !== 'undefined' && navigator.onLine === false) return 'offline'
  return 'unavailable'
}

let counter = 0
const newId = () => `m${Date.now().toString(36)}${(counter++).toString(36)}`

export function useChat(locale: Locale) {
  const [messages, setMessages] = useState<ChatMessage[]>(restore)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<ChatError | null>(null)
  const messagesRef = useRef(messages)
  const controller = useRef<AbortController | null>(null)

  useEffect(() => {
    messagesRef.current = messages
    if (messages.length === 0) removeStorage('session', STORAGE_KEY)
    else writeStorage('session', STORAGE_KEY, JSON.stringify(messages))
  }, [messages])

  useEffect(() => () => controller.current?.abort(), [])

  const ask = useCallback(
    async (history: ChatMessage[]) => {
      const last = history[history.length - 1]
      controller.current?.abort()
      const current = new AbortController()
      controller.current = current
      setSending(true)
      setError(null)
      try {
        const response = await postChat(
          {
            message: last.content,
            locale,
            history: history
              .slice(0, -1)
              .slice(-HISTORY_LIMIT)
              .map(({ role, content }) => ({ role, content })),
            quick_question_id: last.quick,
          },
          current.signal,
        )
        if (current.signal.aborted) return
        setMessages((previous) => [
          ...previous,
          {
            id: newId(),
            role: 'assistant',
            content: response.answer,
            section: response.section ?? undefined,
            messageId: response.message_id,
          },
        ])
      } catch (caught) {
        if (current.signal.aborted) return
        setError(classify(caught))
      } finally {
        if (!current.signal.aborted) setSending(false)
      }
    },
    [locale],
  )

  const send = useCallback(
    (text: string, quick?: QuickQuestionId) => {
      const content = text.trim()
      if (!content || content.length > MAX_LENGTH || sending) return false
      const next: ChatMessage[] = [
        ...messagesRef.current,
        { id: newId(), role: 'user', content, quick },
      ]
      messagesRef.current = next
      setMessages(next)
      void ask(next)
      return true
    },
    [ask, sending],
  )

  const retry = useCallback(() => {
    const history = messagesRef.current
    if (history.length > 0 && history[history.length - 1].role === 'user') void ask(history)
  }, [ask])

  const rate = useCallback(
    async (id: string, helpful: boolean) => {
      const target = messagesRef.current.find((message) => message.id === id)
      if (!target?.messageId || target.rating) return
      const setRating = (rating: ChatMessage['rating']) =>
        setMessages((previous) =>
          previous.map((message) => (message.id === id ? { ...message, rating } : message)),
        )
      // Shown at once; taken back only if the rating can still be sent again later.
      setRating(helpful ? 'up' : 'down')
      try {
        await postFeedback({ message_id: target.messageId, helpful, locale })
      } catch (caught) {
        // 404: the backend never stored this answer, so sending the rating again cannot work.
        if (caught instanceof ApiError && caught.status === 404) return
        setRating(undefined)
      }
    },
    [locale],
  )

  const reset = useCallback(() => {
    controller.current?.abort()
    messagesRef.current = []
    setMessages([])
    setSending(false)
    setError(null)
  }, [])

  return { messages, sending, error, send, retry, rate, reset }
}

export type ChatState = ReturnType<typeof useChat>
