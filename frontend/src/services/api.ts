import type { Locale } from '../data/profile'

const API_URL = import.meta.env.VITE_API_URL

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init.headers },
  })
  if (!response.ok) {
    throw new ApiError(response.status, `Request to ${path} failed with status ${response.status}`)
  }
  return response.json() as Promise<T>
}

export const getHealth = () => request<{ status: string }>('/health')

export type ChatSection = 'projects' | 'experience' | 'about' | 'skills' | 'education' | 'contact'

/** Contract proposed for the future `POST /chat` endpoint (see docs/architecture.md). */
export interface ChatRequest {
  message: string
  locale: Locale
  history: Array<{ role: 'user' | 'assistant'; content: string }>
}

export interface ChatResponse {
  answer: string
  /** Site sections the answer is based on; optional, the backend may not send it at first. */
  sources?: ChatSection[]
}

export function postChat(body: ChatRequest, signal?: AbortSignal): Promise<ChatResponse> {
  // Without a configured backend there is nothing to call: report it as unavailable right away.
  if (!API_URL) return Promise.reject(new ApiError(503, 'VITE_API_URL is not configured'))
  return request<ChatResponse>('/chat', { method: 'POST', body: JSON.stringify(body), signal })
}
