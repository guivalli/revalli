import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type { FilesSummary, Job, RecordFile } from './types'

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
