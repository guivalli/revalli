import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { ChecklistKind } from '../lib/checklists'
import { api } from './client'
import type { ChecklistEntry, ChecklistFacts, ChecklistStatus, Code, CodingUnit, Excerpt } from './types'

const base = (pid: string) => `/projects/${pid}/coding`

export function useCodes(pid: string) {
  return useQuery({ queryKey: ['projects', pid, 'coding', 'codes'], queryFn: () => api.get<Code[]>(`${base(pid)}/codes`) })
}

export function useCodingUnits(pid: string) {
  return useQuery({
    queryKey: ['projects', pid, 'coding', 'units'],
    queryFn: () => api.get<CodingUnit[]>(`${base(pid)}/units`),
  })
}

export function useMatrix(pid: string) {
  return useQuery({
    queryKey: ['projects', pid, 'coding', 'matrix'],
    queryFn: () =>
      api.get<{ units: CodingUnit[]; cells: Record<string, Record<string, number>> }>(`${base(pid)}/matrix`),
  })
}

export function useExcerpts(pid: string, filter: { recordId?: string; codeId?: string }, enabled = true) {
  const qs = new URLSearchParams()
  if (filter.recordId) qs.set('record_id', filter.recordId)
  if (filter.codeId) qs.set('code_id', filter.codeId)
  return useQuery({
    queryKey: ['projects', pid, 'coding', 'excerpts', filter],
    queryFn: () => api.get<Excerpt[]>(`${base(pid)}/excerpts?${qs}`),
    enabled,
  })
}

export const codingExportUrl = (pid: string) => `/api${base(pid)}/export`

export function useCodingActions(pid: string) {
  const qc = useQueryClient()
  const refresh = () => qc.invalidateQueries({ queryKey: ['projects', pid, 'coding'] })
  return {
    createCode: useMutation({
      mutationFn: (body: { name: string; parent_id?: string | null; description?: string; color?: string }) =>
        api.post<Code>(`${base(pid)}/codes`, body),
      onSuccess: refresh,
    }),
    updateCode: useMutation({
      mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) =>
        api.patch<Code>(`${base(pid)}/codes/${id}`, body),
      onSuccess: refresh,
    }),
    deleteCode: useMutation({
      mutationFn: (id: string) => api.delete<void>(`${base(pid)}/codes/${id}`),
      onSuccess: refresh,
    }),
    mergeCode: useMutation({
      mutationFn: ({ id, into }: { id: string; into: string }) =>
        api.post<Code>(`${base(pid)}/codes/${id}/merge`, { into }),
      onSuccess: refresh,
    }),
    createExcerpt: useMutation({
      mutationFn: (body: {
        record_id: string
        text: string
        file_id?: string | null
        page?: number | null
        note?: string
        code_ids: string[]
      }) => api.post<Excerpt>(`${base(pid)}/excerpts`, body),
      onSuccess: refresh,
    }),
    updateExcerpt: useMutation({
      mutationFn: ({ id, body }: { id: string; body: { note?: string; code_ids?: string[] } }) =>
        api.patch<Excerpt>(`${base(pid)}/excerpts/${id}`, body),
      onSuccess: refresh,
    }),
    deleteExcerpt: useMutation({
      mutationFn: (id: string) => api.delete<void>(`${base(pid)}/excerpts/${id}`),
      onSuccess: refresh,
    }),
  }
}

export function useChecklist(pid: string, kind: ChecklistKind) {
  return useQuery({
    queryKey: ['projects', pid, 'checklist', kind],
    queryFn: () =>
      api.get<{ checklist: ChecklistKind; entries: ChecklistEntry[]; facts: ChecklistFacts }>(
        `/projects/${pid}/checklists/${kind}`,
      ),
  })
}

export function useSaveChecklistEntry(pid: string, kind: ChecklistKind) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ item, body }: { item: string; body: { status: ChecklistStatus; location: string; note: string } }) =>
      api.put<ChecklistEntry>(`/projects/${pid}/checklists/${kind}/${item}`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['projects', pid, 'checklist', kind] }),
  })
}

export const checklistExportUrl = (pid: string, kind: ChecklistKind) => `/api/projects/${pid}/checklists/${kind}/export`
