import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type { ApiSource, AssistReply, Job, SourcePreview, SourcesSettings, Translation } from './types'

const base = (pid: string) => `/projects/${pid}/sources`

export function useSourcesSettings(enabled = true) {
  return useQuery({
    queryKey: ['sources', 'settings'],
    queryFn: () => api.get<SourcesSettings>('/sources/settings'),
    enabled,
  })
}

export function useSaveSourcesSettings() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { openalex_api_key?: string; clear_openalex_key?: boolean }) =>
      api.put<SourcesSettings>('/sources/settings', body),
    onSuccess: (data) => qc.setQueryData(['sources', 'settings'], data),
  })
}

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
    assist: useMutation({
      mutationFn: (messages: { role: 'user' | 'assistant'; content: string }[]) =>
        api.post<AssistReply>(`${base(pid)}/assist`, { messages }),
    }),
    translate: useMutation({
      mutationFn: (body: { query: string; target: string }) =>
        api.post<Translation>(`${base(pid)}/translate`, body),
    }),
  }
}
