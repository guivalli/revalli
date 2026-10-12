import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'
import { api } from './client'
import type { DuplicateGroup, Job, RecordPage, Search, Summary } from './types'

export type RecordFilter = 'all' | 'unique' | 'duplicates' | 'missing_abstract'

const base = (pid: string) => `/projects/${pid}`

export function useSummary(pid: string) {
  return useQuery({
    queryKey: ['projects', pid, 'summary'],
    queryFn: () => api.get<Summary>(`${base(pid)}/summary`),
  })
}

export function useSearches(pid: string) {
  return useQuery({
    queryKey: ['projects', pid, 'searches'],
    queryFn: () => api.get<Search[]>(`${base(pid)}/searches`),
  })
}

export function useRecords(
  pid: string,
  params: { q: string; filter: RecordFilter; page: number; searchId?: string },
) {
  const qs = new URLSearchParams({
    q: params.q,
    filter: params.filter,
    page: String(params.page),
    page_size: '25',
  })
  if (params.searchId) qs.set('search_id', params.searchId)
  return useQuery({
    queryKey: ['projects', pid, 'records', params],
    queryFn: () => api.get<RecordPage>(`${base(pid)}/records?${qs}`),
    placeholderData: keepPreviousData,
  })
}

export function useDuplicates(pid: string, status: 'pending' | 'confirmed', page: number) {
  return useQuery({
    queryKey: ['projects', pid, 'duplicates', status, page],
    queryFn: () =>
      api.get<{ items: DuplicateGroup[]; total: number }>(
        `${base(pid)}/duplicates?status=${status}&page=${page}&page_size=10`,
      ),
    placeholderData: keepPreviousData,
  })
}

/** Acompanha as tarefas em andamento e atualiza os dados quando terminam. */
export function useActiveJobs(pid: string) {
  const qc = useQueryClient()
  const query = useQuery({
    queryKey: ['projects', pid, 'jobs', 'active'],
    queryFn: () => api.get<Job[]>(`${base(pid)}/jobs?active=true`),
    refetchInterval: (q) => ((q.state.data?.length ?? 0) > 0 ? 1500 : false),
  })
  const hadActive = useRef(false)
  const active = (query.data?.length ?? 0) > 0
  useEffect(() => {
    if (hadActive.current && !active) void qc.invalidateQueries({ queryKey: ['projects', pid] })
    hadActive.current = active
  }, [active, pid, qc])
  return query
}

export function useCancelJob(pid: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (jobId: string) => api.post<Job>(`${base(pid)}/jobs/${jobId}/cancel`, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['projects', pid, 'jobs'] }),
  })
}

export function useJob(pid: string, id: string | null) {
  return useQuery({
    queryKey: ['projects', pid, 'jobs', 'one', id],
    queryFn: () => api.get<Job>(`${base(pid)}/jobs/${id}`),
    enabled: !!id,
    refetchInterval: (q) =>
      q.state.data && ['done', 'failed'].includes(q.state.data.status) ? false : 1500,
  })
}

export function useRecentJobs(pid: string) {
  return useQuery({
    queryKey: ['projects', pid, 'jobs', 'recent'],
    queryFn: () => api.get<Job[]>(`${base(pid)}/jobs`),
  })
}

export function useRecordActions(pid: string) {
  const qc = useQueryClient()
  const refresh = () => qc.invalidateQueries({ queryKey: ['projects', pid] })
  return {
    importFile: useMutation({
      mutationFn: (form: FormData) =>
        api.upload<{ imported: number; job_id: string | null }>(`${base(pid)}/imports`, form),
      onSuccess: refresh,
    }),
    deleteSearch: useMutation({
      mutationFn: (sid: string) => api.delete<void>(`${base(pid)}/searches/${sid}`),
      onSuccess: refresh,
    }),
    updateSearch: useMutation({
      mutationFn: ({ sid, body }: { sid: string; body: Partial<Search> }) =>
        api.patch<Search>(`${base(pid)}/searches/${sid}`, body),
      onSuccess: refresh,
    }),
    confirm: useMutation({
      mutationFn: ({ gid, primary }: { gid: string; primary: string }) =>
        api.post<DuplicateGroup>(`${base(pid)}/duplicates/${gid}/confirm`, {
          primary_record_id: primary,
        }),
      onSuccess: refresh,
    }),
    reject: useMutation({
      mutationFn: (gid: string) => api.post<void>(`${base(pid)}/duplicates/${gid}/reject`),
      onSuccess: refresh,
    }),
    split: useMutation({
      mutationFn: ({ gid, record }: { gid: string; record: string }) =>
        api.post<DuplicateGroup | null>(`${base(pid)}/duplicates/${gid}/split`, {
          record_id: record,
        }),
      onSuccess: refresh,
    }),
    dedup: useMutation({
      mutationFn: () => api.post<Job>(`${base(pid)}/dedup`),
      onSuccess: refresh,
    }),
    enrich: useMutation({
      mutationFn: () => api.post<Job>(`${base(pid)}/enrich`),
      onSuccess: refresh,
    }),
  }
}
