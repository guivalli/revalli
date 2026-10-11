import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type { GradeRowT, MetaAnalysisT, MetaResult } from './types'

const base = (pid: string) => `/projects/${pid}`

export type AnalysisPayload = Omit<MetaAnalysisT, 'id'>
export type GradePayload = Omit<GradeRowT, 'id' | 'certainty' | 'auto' | 'suggestions'>

export function useAnalyses(pid: string) {
  return useQuery({ queryKey: ['projects', pid, 'meta'], queryFn: () => api.get<MetaAnalysisT[]>(`${base(pid)}/meta`) })
}

export function useMetaResult(pid: string, aid: string | undefined) {
  return useQuery({
    queryKey: ['projects', pid, 'meta', aid, 'result'],
    queryFn: () => api.get<MetaResult>(`${base(pid)}/meta/${aid}/result`),
    enabled: !!aid,
  })
}

export const metaExportUrl = (pid: string, aid: string) => `/api${base(pid)}/meta/${aid}/export`

export function useMetaActions(pid: string) {
  const qc = useQueryClient()
  const refresh = () => qc.invalidateQueries({ queryKey: ['projects', pid] })
  return {
    create: useMutation({
      mutationFn: (body: AnalysisPayload) => api.post<MetaAnalysisT>(`${base(pid)}/meta`, body),
      onSuccess: refresh,
    }),
    update: useMutation({
      mutationFn: ({ id, body }: { id: string; body: AnalysisPayload }) =>
        api.put<MetaAnalysisT>(`${base(pid)}/meta/${id}`, body),
      onSuccess: refresh,
    }),
    remove: useMutation({
      mutationFn: (id: string) => api.delete<void>(`${base(pid)}/meta/${id}`),
      onSuccess: refresh,
    }),
  }
}

export function useGrade(pid: string) {
  return useQuery({ queryKey: ['projects', pid, 'grade'], queryFn: () => api.get<GradeRowT[]>(`${base(pid)}/grade`) })
}

export function useGradeActions(pid: string) {
  const qc = useQueryClient()
  const refresh = () => qc.invalidateQueries({ queryKey: ['projects', pid, 'grade'] })
  return {
    create: useMutation({
      mutationFn: (body: GradePayload) => api.post<GradeRowT>(`${base(pid)}/grade`, body),
      onSuccess: refresh,
    }),
    update: useMutation({
      mutationFn: ({ id, body }: { id: string; body: GradePayload }) => api.put<GradeRowT>(`${base(pid)}/grade/${id}`, body),
      onSuccess: refresh,
    }),
    remove: useMutation({
      mutationFn: (id: string) => api.delete<void>(`${base(pid)}/grade/${id}`),
      onSuccess: refresh,
    }),
  }
}
