export class ApiError extends Error {
  status: number
  code: string

  constructor(status: number, code: string) {
    super(code)
    this.status = status
    this.code = code
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const init: RequestInit = { method, credentials: 'same-origin' }
  const hasBody = method !== 'GET' && !(method === 'DELETE' && body === undefined)
  if (hasBody) {
    // A API exige JSON em toda escrita (proteção contra CSRF)
    init.headers = { 'Content-Type': 'application/json' }
    init.body = JSON.stringify(body ?? {})
  }
  const res = await fetch(`/api${path}`, init)
  if (!res.ok) {
    let code = 'unknown_error'
    try {
      const data = await res.json()
      if (typeof data.detail === 'string') code = data.detail
      else if (Array.isArray(data.detail)) code = 'validation_error'
    } catch {
      /* resposta sem corpo */
    }
    throw new ApiError(res.status, code)
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, body),
  patch: <T>(path: string, body?: unknown) => request<T>('PATCH', path, body),
  delete: <T>(path: string) => request<T>('DELETE', path),
}
