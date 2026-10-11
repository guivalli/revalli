import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type { Job, Watch, WatchInput } from './types'

const base = (pid: string) => `/projects/${pid}/watches`

export function useWatches(pid: string) {
  return useQuery({
    queryKey: ['projects', pid, 'watches'],
    queryFn: () => api.get<Watch[]>(base(pid)),
  })
}

export function useWatchActions(pid: string) {
  const qc = useQueryClient()
  const refresh = () => qc.invalidateQueries({ queryKey: ['projects', pid] })
  return {
    create: useMutation({
      mutationFn: (body: WatchInput) => api.post<Watch>(base(pid), body),
      onSuccess: refresh,
    }),
    update: useMutation({
      mutationFn: ({ id, body }: { id: string; body: WatchInput }) =>
        api.put<Watch>(`${base(pid)}/${id}`, body),
      onSuccess: refresh,
    }),
    remove: useMutation({
      mutationFn: (id: string) => api.delete<void>(`${base(pid)}/${id}`),
      onSuccess: refresh,
    }),
    run: useMutation({
      mutationFn: (id: string) => api.post<Job>(`${base(pid)}/${id}/run`, {}),
      onSuccess: refresh,
    }),
  }
}
