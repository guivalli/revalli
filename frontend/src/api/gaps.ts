import { useQuery } from '@tanstack/react-query'
import { api } from './client'
import type { GapDimensions, GapMap } from './types'

const base = (pid: string) => `/projects/${pid}/gaps`

export function useGapDimensions(pid: string) {
  return useQuery({
    queryKey: ['projects', pid, 'gaps', 'dimensions'],
    queryFn: () => api.get<GapDimensions>(`${base(pid)}/dimensions`),
  })
}

export function useGapMap(pid: string, rows: string, cols: string) {
  const qs = new URLSearchParams({ rows, cols }).toString()
  return useQuery({
    queryKey: ['projects', pid, 'gaps', rows, cols],
    queryFn: () => api.get<GapMap>(`${base(pid)}?${qs}`),
    enabled: !!rows && !!cols,
  })
}

export const gapExportUrl = (pid: string, rows: string, cols: string) =>
  `/api${base(pid)}/export?` + new URLSearchParams({ rows, cols }).toString()
