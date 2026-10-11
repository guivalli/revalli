import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, api } from './client'

afterEach(() => vi.restoreAllMocks())

describe('api client', () => {
  it('envia JSON nas escritas', async () => {
    const spy = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(new Response(JSON.stringify({ ok: 1 }), { status: 200 }))
    await api.post('/x', { a: 1 })
    const [url, init] = spy.mock.calls[0]
    expect(url).toBe('/api/x')
    expect(init?.headers).toEqual({ 'Content-Type': 'application/json' })
    expect(init?.body).toBe('{"a":1}')
  })

  it('logout sem corpo ainda envia JSON vazio', async () => {
    const spy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(null, { status: 204 }))
    await api.post('/auth/logout')
    expect(spy.mock.calls[0][1]?.body).toBe('{}')
  })

  it('converte o detail da API em ApiError', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ detail: 'invalid_credentials' }), { status: 401 }),
    )
    await expect(api.post('/auth/login', {})).rejects.toMatchObject({
      status: 401,
      code: 'invalid_credentials',
    })
    expect(new ApiError(1, 'x')).toBeInstanceOf(Error)
  })
})
