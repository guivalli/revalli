import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type {
  FilesSummary,
  Job,
  PendingFile,
  RecordFile,
  Study,
  StudyCandidate,
  StudySuggestion,
} from './types'

export const fileUrl = (pid: string, fid: string) => `/api/projects/${pid}/files/${fid}/content`

export function useRecordFiles(pid: string, rid: string | null) {
  return useQuery({
    queryKey: ['projects', pid, 'files', 'record', rid],
    queryFn: () => api.get<RecordFile[]>(`/projects/${pid}/records/${rid}/files`),
    enabled: !!rid,
  })
}

export function useFilesSummary(pid: string) {
  return useQuery({
    queryKey: ['projects', pid, 'files', 'summary'],
    queryFn: () => api.get<FilesSummary>(`/projects/${pid}/files/summary`),
  })
}

export const pendingCsvUrl = (pid: string) => `/api/projects/${pid}/files/pending.csv`

export function usePendingFiles(pid: string) {
  return useQuery({
    queryKey: ['projects', pid, 'files', 'pending'],
    queryFn: () => api.get<PendingFile[]>(`/projects/${pid}/files/pending`),
  })
}

export function useFileActions(pid: string) {
  const qc = useQueryClient()
  const refresh = () => qc.invalidateQueries({ queryKey: ['projects', pid, 'files'] })
  const jobs = () => qc.invalidateQueries({ queryKey: ['projects', pid, 'jobs'] })
  return {
    upload: useMutation({
      mutationFn: ({ rid, file }: { rid: string; file: File }) => {
        const form = new FormData()
        form.append('file', file)
        return api.upload<RecordFile>(`/projects/${pid}/records/${rid}/files`, form)
      },
      onSuccess: refresh,
    }),
    remove: useMutation({
      mutationFn: (fid: string) => api.delete<void>(`/projects/${pid}/files/${fid}`),
      onSuccess: refresh,
    }),
    makeMain: useMutation({
      mutationFn: (fid: string) => api.post<RecordFile>(`/projects/${pid}/files/${fid}/main`, {}),
      onSuccess: refresh,
    }),
    zip: useMutation({
      mutationFn: (file: File) => {
        const form = new FormData()
        form.append('file', file)
        return api.upload<Job>(`/projects/${pid}/files/zip`, form)
      },
      onSuccess: () => {
        void refresh()
        void jobs()
      },
    }),
    openAccess: useMutation({
      mutationFn: () => api.post<Job>(`/projects/${pid}/files/open-access`, {}),
      onSuccess: jobs,
    }),
  }
}

// --- Estudos com vários relatórios ---------------------------------------------------

export function useStudies(pid: string) {
  return useQuery({
    queryKey: ['projects', pid, 'studies', 'list'],
    queryFn: () => api.get<Study[]>(`/projects/${pid}/studies`),
  })
}

export function useStudySuggestions(pid: string) {
  return useQuery({
    queryKey: ['projects', pid, 'studies', 'suggestions'],
    queryFn: () => api.get<StudySuggestion[]>(`/projects/${pid}/studies/suggestions`),
  })
}

export function useStudyCandidates(pid: string, q: string, enabled: boolean) {
  return useQuery({
    queryKey: ['projects', pid, 'studies', 'candidates', q],
    queryFn: () =>
      api.get<StudyCandidate[]>(`/projects/${pid}/studies/candidates?q=${encodeURIComponent(q)}`),
    enabled,
    placeholderData: keepPreviousData,
  })
}

export function useStudyActions(pid: string) {
  const qc = useQueryClient()
  const refresh = () => qc.invalidateQueries({ queryKey: ['projects', pid] })
  return {
    create: useMutation({
      mutationFn: (body: { record_ids: string[]; label?: string }) =>
        api.post<Study>(`/projects/${pid}/studies`, body),
      onSuccess: refresh,
    }),
    update: useMutation({
      mutationFn: ({ sid, ...body }: { sid: string; label?: string; primary_record_id?: string }) =>
        api.patch<Study>(`/projects/${pid}/studies/${sid}`, body),
      onSuccess: refresh,
    }),
    removeReport: useMutation({
      mutationFn: ({ sid, rid }: { sid: string; rid: string }) =>
        api.delete<void>(`/projects/${pid}/studies/${sid}/reports/${rid}`),
      onSuccess: refresh,
    }),
    remove: useMutation({
      mutationFn: (sid: string) => api.delete<void>(`/projects/${pid}/studies/${sid}`),
      onSuccess: refresh,
    }),
  }
}
