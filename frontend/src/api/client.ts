export class ApiError extends Error {
  status: number
  code: string

  constructor(status: number, code: string) {
    super(code)
    this.status = status
    this.code = code
  }
}

async function handle<T>(res: Response): Promise<T> {
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

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const init: RequestInit = { method, credentials: 'same-origin' }
  const hasBody = method !== 'GET' && !(method === 'DELETE' && body === undefined)
  if (hasBody) {
    // A API exige JSON em toda escrita (proteção contra CSRF)
    init.headers = { 'Content-Type': 'application/json' }
    init.body = JSON.stringify(body ?? {})
  }
  return handle<T>(await fetch(`/api${path}`, init))
}

async function upload<T>(path: string, form: FormData): Promise<T> {
  // O cabeçalho X-Requested-With libera o upload na proteção contra CSRF da API
  const res = await fetch(`/api${path}`, {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'X-Requested-With': 'ReValli' },
    body: form,
  })
  return handle<T>(res)
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, body),
  patch: <T>(path: string, body?: unknown) => request<T>('PATCH', path, body),
  delete: <T>(path: string) => request<T>('DELETE', path),
  upload,
}
