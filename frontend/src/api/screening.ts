import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type {
  ConflictItem,
  DecisionInfo,
  DecisionKind,
  PairAgreement,
  Phase,
  Progress,
  Reason,
  ScreenedItem,
  ScreeningItem,
  ScreeningSettings,
} from './types'

const base = (pid: string) => `/projects/${pid}/screening`

export function useScreeningSettings(pid: string) {
  return useQuery({
    queryKey: ['projects', pid, 'screening', 'settings'],
    queryFn: () => api.get<ScreeningSettings>(`${base(pid)}/settings`),
  })
}

export function useReasons(pid: string) {
  return useQuery({
    queryKey: ['projects', pid, 'screening', 'reasons'],
    queryFn: () => api.get<Reason[]>(`${base(pid)}/reasons`),
  })
}

export function useLabels(pid: string) {
  return useQuery({
    queryKey: ['projects', pid, 'screening', 'labels'],
    queryFn: () => api.get<string[]>(`${base(pid)}/labels`),
  })
}

export function useProgress(pid: string, phase: Phase) {
  return useQuery({
    queryKey: ['projects', pid, 'screening', phase, 'progress'],
    queryFn: () => api.get<Progress>(`${base(pid)}/${phase}/progress`),
  })
}

export function useAgreement(pid: string, phase: Phase) {
  return useQuery({
    queryKey: ['projects', pid, 'screening', phase, 'agreement'],
    queryFn: () => api.get<{ pairs: PairAgreement[] }>(`${base(pid)}/${phase}/agreement`),
  })
}

export function useQueue(pid: string, phase: Phase) {
  return useQuery({
    queryKey: ['projects', pid, 'screening', phase, 'queue'],
    queryFn: () =>
      api.get<{ items: ScreeningItem[]; remaining: number }>(`${base(pid)}/${phase}/queue?limit=30`),
    refetchOnWindowFocus: false,
  })
}

export function useConflicts(pid: string, phase: Phase, page: number, enabled: boolean) {
  return useQuery({
    queryKey: ['projects', pid, 'screening', phase, 'conflicts', page],
    queryFn: () =>
      api.get<{ items: ConflictItem[]; total: number }>(
        `${base(pid)}/${phase}/conflicts?page=${page}&page_size=10`,
      ),
    enabled,
    retry: false,
    placeholderData: keepPreviousData,
  })
}

export function useScreened(
  pid: string,
  phase: Phase,
  state: string,
  page: number,
  decision?: DecisionKind,
) {
  const qs = new URLSearchParams({ state, page: String(page), page_size: '20' })
  if (decision) qs.set('decision', decision)
  return useQuery({
    queryKey: ['projects', pid, 'screening', phase, 'screened', state, decision, page],
    queryFn: () =>
      api.get<{ items: ScreenedItem[]; total: number }>(`${base(pid)}/${phase}/screened?${qs}`),
    placeholderData: keepPreviousData,
  })
}

export interface DecisionPayload {
  record_id: string
  decision: DecisionKind | null
  reason_ids?: string[]
  labels?: string[]
  note?: string
}

export function useScreeningActions(pid: string, phase: Phase) {
  const qc = useQueryClient()
  const refreshStats = () => {
    void qc.invalidateQueries({ queryKey: ['projects', pid, 'screening', phase, 'progress'] })
    void qc.invalidateQueries({ queryKey: ['projects', pid, 'screening', phase, 'screened'] })
    void qc.invalidateQueries({ queryKey: ['projects', pid, 'screening', 'labels'] })
    // A sugestão da IA fica visível depois que o revisor decide
    void qc.invalidateQueries({ queryKey: ['projects', pid, 'ai', phase, 'suggestions'] })
  }
  return {
    decide: useMutation({
      mutationFn: (body: DecisionPayload) =>
        api.post<DecisionInfo | null>(`${base(pid)}/${phase}/decisions`, body),
      onSuccess: refreshStats,
    }),
    resolve: useMutation({
      mutationFn: (body: DecisionPayload) =>
        api.post<DecisionInfo | null>(`${base(pid)}/${phase}/resolve`, body),
      onSuccess: () => {
        refreshStats()
        void qc.invalidateQueries({ queryKey: ['projects', pid, 'screening', phase, 'conflicts'] })
      },
    }),
  }
}

export function useSettingsActions(pid: string) {
  const qc = useQueryClient()
  const refresh = () => qc.invalidateQueries({ queryKey: ['projects', pid, 'screening'] })
  return {
    save: useMutation({
      mutationFn: (s: ScreeningSettings) => api.put<ScreeningSettings>(`${base(pid)}/settings`, s),
      onSuccess: refresh,
    }),
    addReason: useMutation({
      mutationFn: (label: string) => api.post<Reason>(`${base(pid)}/reasons`, { label }),
      onSuccess: refresh,
    }),
    updateReason: useMutation({
      mutationFn: ({ id, ...body }: Partial<Reason> & { id: string }) =>
        api.patch<Reason>(`${base(pid)}/reasons/${id}`, body),
      onSuccess: refresh,
    }),
  }
}
