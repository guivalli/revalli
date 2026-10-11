import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type {
  ComparisonT,
  ExtractionFormT,
  ExtractionT,
  FieldDef,
  FieldValue,
  Job,
  QuoteT,
  RobSummaryT,
  UnitDetailT,
  UnitT,
} from './types'

const base = (pid: string) => `/projects/${pid}/extraction`

export const exportUrl = (pid: string, fid: string, layout: 'wide' | 'long') =>
  `/api${base(pid)}/forms/${fid}/export?layout=${layout}`

export function useForms(pid: string) {
  return useQuery({
    queryKey: ['projects', pid, 'extraction', 'forms'],
    queryFn: () => api.get<ExtractionFormT[]>(`${base(pid)}/forms`),
  })
}

export function useForm(pid: string, fid: string | undefined) {
  return useQuery({
    queryKey: ['projects', pid, 'extraction', 'form', fid],
    queryFn: () => api.get<ExtractionFormT>(`${base(pid)}/forms/${fid}`),
    enabled: !!fid,
  })
}

export function useUnits(pid: string, fid: string | undefined) {
  return useQuery({
    queryKey: ['projects', pid, 'extraction', 'units', fid],
    queryFn: () => api.get<UnitT[]>(`${base(pid)}/forms/${fid}/units`),
    enabled: !!fid,
  })
}

export function useUnit(pid: string, fid: string, rid: string) {
  return useQuery({
    queryKey: ['projects', pid, 'extraction', 'unit', fid, rid],
    queryFn: () => api.get<UnitDetailT>(`${base(pid)}/forms/${fid}/units/${rid}`),
  })
}

export function useComparison(pid: string, fid: string, rid: string, enabled: boolean) {
  return useQuery({
    queryKey: ['projects', pid, 'extraction', 'compare', fid, rid],
    queryFn: () => api.get<ComparisonT>(`${base(pid)}/forms/${fid}/units/${rid}/compare`),
    enabled,
  })
}

export function useRob(pid: string, fid: string | undefined, enabled: boolean) {
  return useQuery({
    queryKey: ['projects', pid, 'extraction', 'rob', fid],
    queryFn: () => api.get<RobSummaryT>(`${base(pid)}/forms/${fid}/rob`),
    enabled: enabled && !!fid,
  })
}

export interface FormBody {
  name: string
  kind: 'extraction' | 'rob'
  extractors: number
  fields: FieldDef[]
}

export interface ExtractionBody {
  values: Record<string, FieldValue>
  quotes?: Record<string, QuoteT>
  status: 'draft' | 'done'
}

export function useFormActions(pid: string) {
  const qc = useQueryClient()
  const refresh = () => qc.invalidateQueries({ queryKey: ['projects', pid, 'extraction'] })
  return {
    create: useMutation({
      mutationFn: (body: FormBody) => api.post<ExtractionFormT>(`${base(pid)}/forms`, body),
      onSuccess: refresh,
    }),
    fromTemplate: useMutation({
      mutationFn: (body: { template: string; extractors: number }) =>
        api.post<ExtractionFormT>(`${base(pid)}/forms/template`, body),
      onSuccess: refresh,
    }),
    update: useMutation({
      mutationFn: ({ fid, body }: { fid: string; body: FormBody }) =>
        api.put<ExtractionFormT>(`${base(pid)}/forms/${fid}`, body),
      onSuccess: refresh,
    }),
    remove: useMutation({
      mutationFn: (fid: string) => api.delete<void>(`${base(pid)}/forms/${fid}`),
      onSuccess: refresh,
    }),
    runAI: useMutation({
      mutationFn: ({ fid, ...body }: { fid: string; record_ids?: string[]; overwrite?: boolean }) =>
        api.post<Job>(`${base(pid)}/forms/${fid}/ai`, body),
      onSuccess: () => qc.invalidateQueries({ queryKey: ['projects', pid] }),
    }),
  }
}

export function useExtractionActions(pid: string, fid: string, rid: string) {
  const qc = useQueryClient()
  const refresh = () => qc.invalidateQueries({ queryKey: ['projects', pid, 'extraction'] })
  return {
    saveMine: useMutation({
      mutationFn: (body: ExtractionBody) =>
        api.put<ExtractionT>(`${base(pid)}/forms/${fid}/units/${rid}/mine`, body),
      onSuccess: refresh,
    }),
    saveConsensus: useMutation({
      mutationFn: (body: ExtractionBody) =>
        api.put<ExtractionT>(`${base(pid)}/forms/${fid}/units/${rid}/consensus`, body),
      onSuccess: refresh,
    }),
    removeConsensus: useMutation({
      mutationFn: () => api.delete<void>(`${base(pid)}/forms/${fid}/units/${rid}/consensus`),
      onSuccess: refresh,
    }),
  }
}
