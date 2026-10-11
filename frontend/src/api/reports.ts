import { useQuery } from '@tanstack/react-query'
import { api } from './client'
import type { Prisma } from './types'

export function usePrisma(pid: string) {
  return useQuery({
    queryKey: ['projects', pid, 'report', 'prisma'],
    queryFn: () => api.get<Prisma>(`/projects/${pid}/report/prisma`),
  })
}

export function exportUrl(pid: string, format: 'ris' | 'csv', phase: string, state: string) {
  const qs = new URLSearchParams({ format, phase, state })
  return `/api/projects/${pid}/export?${qs}`
}
