import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type {
  AICalibration,
  AIFlag,
  AIEstimate,
  AIScope,
  AISuggestion,
  AIUsage,
  InstanceAISettings,
  Job,
  Phase,
  ProjectAISettings,
  Provider,
  ProviderKind,
} from './types'

export interface ProviderPayload {
  name: string
  kind: ProviderKind
  base_url: string
  api_key?: string
  clear_api_key?: boolean
  is_local: boolean
}

export function useProviders(enabled = true) {
  return useQuery({
    queryKey: ['ai', 'providers'],
    queryFn: () => api.get<Provider[]>('/ai/providers'),
    enabled,
  })
}

export function useInstanceAI() {
  return useQuery({ queryKey: ['ai', 'settings'], queryFn: () => api.get<InstanceAISettings>('/ai/settings') })
}

export function useProviderActions() {
  const qc = useQueryClient()
  const refresh = () => qc.invalidateQueries({ queryKey: ['ai'] })
  return {
    create: useMutation({
      mutationFn: (body: ProviderPayload) => api.post<Provider>('/ai/providers', body),
      onSuccess: refresh,
    }),
    update: useMutation({
      mutationFn: ({ id, body }: { id: string; body: ProviderPayload }) =>
        api.put<Provider>(`/ai/providers/${id}`, body),
      onSuccess: refresh,
    }),
    remove: useMutation({
      mutationFn: (id: string) => api.delete<void>(`/ai/providers/${id}`),
      onSuccess: refresh,
    }),
    test: useMutation({ mutationFn: (id: string) => api.post<string[]>(`/ai/providers/${id}/test`, {}) }),
    saveSettings: useMutation({
      mutationFn: (s: InstanceAISettings) => api.put<InstanceAISettings>('/ai/settings', s),
      onSuccess: refresh,
    }),
  }
}

const base = (pid: string) => `/projects/${pid}/ai`

export function useProjectAI(pid: string) {
  return useQuery({
    queryKey: ['projects', pid, 'ai', 'settings'],
    queryFn: () => api.get<ProjectAISettings>(`${base(pid)}/settings`),
  })
}

export function useAIUsage(pid: string) {
  return useQuery({
    queryKey: ['projects', pid, 'ai', 'usage'],
    queryFn: () => api.get<AIUsage>(`${base(pid)}/usage`),
  })
}

export function useCalibration(pid: string, phase: Phase) {
  return useQuery({
    queryKey: ['projects', pid, 'ai', phase, 'calibration'],
    queryFn: () => api.get<AICalibration>(`${base(pid)}/${phase}/calibration`),
  })
}

export function useAIFlags(pid: string, phase: Phase, enabled: boolean) {
  return useQuery({
    queryKey: ['projects', pid, 'ai', phase, 'flags'],
    queryFn: () => api.get<AIFlag[]>(`${base(pid)}/${phase}/flags`),
    enabled,
  })
}

export function useSuggestions(pid: string, phase: Phase, ids: string[], enabled = true) {
  const key = [...ids].sort().join(',')
  return useQuery({
    queryKey: ['projects', pid, 'ai', phase, 'suggestions', key],
    queryFn: () => api.get<AISuggestion[]>(`${base(pid)}/${phase}/suggestions?ids=${key}`),
    enabled: enabled && ids.length > 0,
    select: (rows) => new Map(rows.map((s) => [s.record_id, s])),
  })
}

export interface RunPayload {
  phase: Phase
  scope: AIScope
  limit?: number | null
}

export function useProjectAIActions(pid: string) {
  const qc = useQueryClient()
  return {
    save: useMutation({
      mutationFn: (s: ProjectAISettings) => api.put<ProjectAISettings>(`${base(pid)}/settings`, s),
      onSuccess: () => qc.invalidateQueries({ queryKey: ['projects', pid, 'ai'] }),
    }),
    estimate: useMutation({ mutationFn: (body: RunPayload) => api.post<AIEstimate>(`${base(pid)}/estimate`, body) }),
    run: useMutation({
      mutationFn: (body: RunPayload) => api.post<Job>(`${base(pid)}/run`, body),
      onSuccess: () => qc.invalidateQueries({ queryKey: ['projects', pid, 'jobs'] }),
    }),
  }
}

export function useAIBot(pid: string, enabled = true) {
  return useQuery({
    queryKey: ['projects', pid, 'ai', 'bot'],
    queryFn: () => api.get<{ user_id: string }>(`${base(pid)}/bot`),
    enabled,
    staleTime: Infinity,
  })
}
