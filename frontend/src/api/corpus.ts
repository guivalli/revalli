import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type { CorpusMessage, CorpusStatus, Job } from './types'

const base = (pid: string) => `/projects/${pid}/corpus`

/** Ainda há PDFs sem trechos, ou trechos sem vetor (quando há modelo de embeddings). */
export const indexIncomplete = (s: CorpusStatus) =>
  s.pending_files > 0 || (s.embeddings_model !== null && s.embedded < s.chunks)

/** Com `poll`, consulta de novo enquanto a indexação não termina. */
export function useCorpusStatus(pid: string, poll: boolean) {
  return useQuery({
    queryKey: ['projects', pid, 'corpus', 'status'],
    queryFn: () => api.get<CorpusStatus>(`${base(pid)}/status`),
    refetchInterval: (q) => (poll && (!q.state.data || indexIncomplete(q.state.data)) ? 3000 : false),
  })
}

export function useCorpusMessages(pid: string) {
  return useQuery({
    queryKey: ['projects', pid, 'corpus', 'messages'],
    queryFn: () => api.get<CorpusMessage[]>(`${base(pid)}/messages`),
  })
}

export function useCorpusActions(pid: string) {
  const qc = useQueryClient()
  const refresh = () => qc.invalidateQueries({ queryKey: ['projects', pid, 'corpus'] })
  return {
    index: useMutation({
      mutationFn: () => api.post<Job>(`${base(pid)}/index`, {}),
      onSuccess: refresh,
    }),
    ask: useMutation({
      mutationFn: (body: { question: string; scope: 'included' | 'all'; follow_up: boolean }) =>
        api.post<CorpusMessage>(`${base(pid)}/ask`, body),
      onSuccess: refresh,
    }),
    remove: useMutation({
      mutationFn: (id: string) => api.delete<void>(`${base(pid)}/messages/${id}`),
      onSuccess: refresh,
    }),
  }
}
