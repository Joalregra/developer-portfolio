import { useCallback, useEffect, useRef, useState } from 'react'
import type { Locale } from '../../data/profile'
import { readStorage, removeStorage, writeStorage } from '../../lib/storage'
import { ApiError, postChat, type ChatSection } from '../../services/api'

export const MAX_LENGTH = 1000
export const COUNTER_FROM = 800
const STORAGE_KEY = 'chat:v1'
const HISTORY_LIMIT = 10

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: ChatSection[]
}

export type ChatError = 'unavailable' | 'rateLimit' | 'offline'

function restore(): ChatMessage[] {
  const raw = readStorage('session', STORAGE_KEY)
  if (!raw) return []
  try {
    const parsed: unknown = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed.filter(
      (item): item is ChatMessage =>
        typeof item === 'object' &&
        item !== null &&
        typeof item.id === 'string' &&
        (item.role === 'user' || item.role === 'assistant') &&
        typeof item.content === 'string',
    )
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
          },
          current.signal,
        )
        if (current.signal.aborted) return
        setMessages((previous) => [
          ...previous,
          { id: newId(), role: 'assistant', content: response.answer, sources: response.sources },
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
    (text: string) => {
      const content = text.trim()
      if (!content || content.length > MAX_LENGTH || sending) return false
      const next = [...messagesRef.current, { id: newId(), role: 'user' as const, content }]
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

  const reset = useCallback(() => {
    controller.current?.abort()
    messagesRef.current = []
    setMessages([])
    setSending(false)
    setError(null)
  }, [])

  return { messages, sending, error, send, retry, reset }
}

export type ChatState = ReturnType<typeof useChat>
