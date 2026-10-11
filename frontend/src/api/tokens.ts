import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type { ApiTokenCreated, ApiTokenInfo } from './types'

export function useApiTokens() {
  return useQuery({ queryKey: ['tokens'], queryFn: () => api.get<ApiTokenInfo[]>('/tokens') })
}

export function useApiTokenActions() {
  const qc = useQueryClient()
  const refresh = () => qc.invalidateQueries({ queryKey: ['tokens'] })
  return {
    create: useMutation({
      mutationFn: (body: { name: string; project_id: string | null; expires_in_days: number | null }) =>
        api.post<ApiTokenCreated>('/tokens', body),
      onSuccess: refresh,
    }),
    revoke: useMutation({
      mutationFn: (id: string) => api.delete<void>(`/tokens/${id}`),
      onSuccess: refresh,
    }),
  }
}
