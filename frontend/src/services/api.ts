import type { Locale } from '../data/profile'

const API_URL = import.meta.env.VITE_API_URL

export class ApiError extends Error {
  readonly status: number
  /** Stable code from the backend error body (for example `rate_limited`); empty if there is none. */
  readonly code: string

  constructor(status: number, message: string, code = '') {
    super(message)
    this.status = status
    this.code = code
  }
}

/** Reads `error.code` from the backend's uniform error body, without ever throwing. */
async function errorCode(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json()
    const code = (body as { error?: { code?: unknown } })?.error?.code
    return typeof code === 'string' ? code : ''
  } catch {
    return ''
  }
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init.headers },
  })
  if (!response.ok) {
    throw new ApiError(
      response.status,
      `Request to ${path} failed with status ${response.status}`,
      await errorCode(response),
    )
  }
  return response.json() as Promise<T>
}

export const getHealth = () => request<{ status: string }>('/health')

export type ChatSection = 'projects' | 'experience' | 'about' | 'skills' | 'education' | 'contact'

/** Ids of the quick-question buttons. The backend answers them without calling a model. */
export type QuickQuestionId =
  'projects' | 'stack' | 'production' | 'availability' | 'challenge' | 'ai'

const QUICK_QUESTION_IDS: readonly string[] = [
  'projects',
  'stack',
  'production',
  'availability',
  'challenge',
  'ai',
]

export function toQuickQuestionId(id: string): QuickQuestionId | undefined {
  return QUICK_QUESTION_IDS.includes(id) ? (id as QuickQuestionId) : undefined
}

/** Contract of `POST /api/chat` (see docs/architecture.md). */
export interface ChatRequest {
  message: string
  locale: Locale
  history: Array<{ role: 'user' | 'assistant'; content: string }>
  quick_question_id?: QuickQuestionId
}

export interface ChatResponse {
  answer: string
  /** True when the question was off topic or looked like an attack: `answer` is a fixed refusal. */
  refused: boolean
  /** Section of the page the answer is based on, if any. */
  section: ChatSection | null
  message_id: string
  request_id: string
}

/** The backend stops a chat at 25 s; the browser gives up a little later. */
const CHAT_TIMEOUT_MS = 30_000

function withTimeout(signal?: AbortSignal): AbortSignal {
  const timeout = AbortSignal.timeout(CHAT_TIMEOUT_MS)
  return signal ? AbortSignal.any([signal, timeout]) : timeout
}

export function postChat(body: ChatRequest, signal?: AbortSignal): Promise<ChatResponse> {
  // Without a configured backend there is nothing to call: report it as unavailable right away.
  if (!API_URL) return Promise.reject(new ApiError(503, 'VITE_API_URL is not configured'))
  return request<ChatResponse>('/api/chat', {
    method: 'POST',
    body: JSON.stringify(body),
    signal: withTimeout(signal),
  })
}
