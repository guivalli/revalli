export type Role = 'lead' | 'reviewer' | 'arbitrator' | 'extractor' | 'observer'
export const ROLES: Role[] = ['lead', 'reviewer', 'arbitrator', 'extractor', 'observer']

export type ReviewType = 'systematic' | 'scoping' | 'integrative' | 'other'
export const REVIEW_TYPES: ReviewType[] = ['systematic', 'scoping', 'integrative', 'other']

export interface User {
  id: string
  email: string
  full_name: string
  is_admin: boolean
  locale: string
}

export interface Project {
  id: string
  title: string
  description: string
  review_type: ReviewType
  created_at: string
  my_role: Role | null
  member_count: number
}

export interface Member {
  user_id: string
  email: string
  full_name: string
  role: Role
  joined_at: string
}

export interface InvitationCreated {
  id: string
  email: string
  invite_url: string
  expires_at: string
}

export interface InvitationInfo {
  email: string
  project_title: string | null
  role: Role | null
  account_exists: boolean
}

export interface Search {
  id: string
  source: string
  query: string
  searched_on: string | null
  notes: string
  file_name: string
  file_format: string
  reported_count: number | null
  imported_count: number
  created_at: string
}

export interface RecordItem {
  id: string
  search_id: string | null
  title: string
  abstract: string
  authors: string[]
  year: number | null
  journal: string
  volume: string
  issue: string
  pages: string
  doi: string | null
  pmid: string | null
  url: string
  keywords: string[]
  language: string
  publication_type: string
  enriched: Record<string, string>
  duplicate_group_id: string | null
  is_duplicate: boolean
}

export interface RecordPage {
  items: RecordItem[]
  total: number
  page: number
  page_size: number
}

export interface DuplicateGroup {
  id: string
  status: 'pending' | 'confirmed'
  method: 'doi' | 'pmid' | 'title'
  score: number
  primary_record_id: string | null
  records: RecordItem[]
}

export interface Job {
  id: string
  kind: 'dedup' | 'enrich'
  status: 'queued' | 'running' | 'done' | 'failed'
  progress: number
  total: number
  result: Record<string, unknown>
  error: string
  created_at: string
  finished_at: string | null
}

export interface Summary {
  records_total: number
  duplicates_removed: number
  records_unique: number
  pending_groups: number
  missing_abstract: number
  by_source: { source: string; records: number }[]
}
