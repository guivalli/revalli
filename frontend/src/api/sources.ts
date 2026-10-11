import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type { ApiSource, Job, SourcePreview, Translation } from './types'

const base = (pid: string) => `/projects/${pid}/sources`

export function useSnowballInfo(pid: string) {
  return useQuery({
    queryKey: ['projects', pid, 'sources', 'snowball'],
    queryFn: () => api.get<{ included: number; enabled: boolean }>(`${base(pid)}/snowball`),
  })
}

export function useSourceActions(pid: string) {
  const qc = useQueryClient()
  const refresh = () => qc.invalidateQueries({ queryKey: ['projects', pid] })
  return {
    preview: useMutation({
      mutationFn: (body: { source: ApiSource; query: string }) =>
        api.post<SourcePreview>(`${base(pid)}/preview`, body),
    }),
    search: useMutation({
      mutationFn: (body: { source: ApiSource; query: string; limit: number }) =>
        api.post<Job>(`${base(pid)}/search`, body),
      onSuccess: refresh,
    }),
    snowball: useMutation({
      mutationFn: (body: { direction: 'backward' | 'forward' | 'both'; record_ids?: string[] }) =>
        api.post<Job>(`${base(pid)}/snowball`, body),
      onSuccess: refresh,
    }),
    translate: useMutation({
      mutationFn: (body: { query: string; target: string }) =>
        api.post<Translation>(`${base(pid)}/translate`, body),
    }),
  }
}
