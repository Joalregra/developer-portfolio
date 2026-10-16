import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, request, toQuickQuestionId } from './api'

afterEach(() => {
  vi.unstubAllGlobals()
})

function stubFetch(response: Response) {
  const fetchMock = vi.fn().mockResolvedValue(response)
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('request', () => {
  it('keeps the stable error code of the backend on the ApiError', async () => {
    stubFetch(
      new Response(
        JSON.stringify({ error: { code: 'rate_limited', message: 'x', request_id: 'r' } }),
        { status: 429 },
      ),
    )

    const failure = await request('/api/chat').catch((error: unknown) => error)

    expect(failure).toBeInstanceOf(ApiError)
    expect(failure).toMatchObject({ status: 429, code: 'rate_limited' })
  })

  it('still throws an ApiError when the body is not the backend error shape', async () => {
    stubFetch(new Response('<html>Bad gateway</html>', { status: 502 }))

    const failure = await request('/x').catch((error: unknown) => error)

    expect(failure).toMatchObject({ status: 502, code: '' })
  })

  it('returns the parsed body on success', async () => {
    stubFetch(new Response(JSON.stringify({ status: 'ok' }), { status: 200 }))

    await expect(request('/health')).resolves.toEqual({ status: 'ok' })
  })

  it('resolves with nothing on a 204, which has no body to parse', async () => {
    stubFetch(new Response(null, { status: 204 }))

    await expect(request('/api/chat/feedback')).resolves.toBeUndefined()
  })
})

describe('toQuickQuestionId', () => {
  it('accepts the six button ids and rejects anything else', () => {
    expect(toQuickQuestionId('availability')).toBe('availability')
    expect(toQuickQuestionId('ai')).toBe('ai')
    expect(toQuickQuestionId('contact')).toBeUndefined()
    expect(toQuickQuestionId('')).toBeUndefined()
  })
})
