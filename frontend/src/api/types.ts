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
  kind: 'dedup' | 'enrich' | 'ai_screen' | 'ai_embed' | 'pdf_zip' | 'pdf_oa'
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

export type Phase = 'title_abstract' | 'full_text'
export type DecisionKind = 'include' | 'exclude' | 'maybe'

export interface ScreeningSettings {
  blind: boolean
  reviewers_title_abstract: number
  reviewers_full_text: number
  inclusion_criteria: string
  exclusion_criteria: string
  highlight_include: string[]
  highlight_exclude: string[]
}

export interface Reason {
  id: string
  label: string
  position: number
  archived: boolean
}

export interface DecisionInfo {
  user_id: string | null
  user_name: string | null
  decision: DecisionKind
  reason_ids: string[]
  labels: string[]
  note: string
  is_final: boolean
  created_at: string
}

export interface ScreeningItem {
  id: string
  title: string
  abstract: string
  authors: string[]
  year: number | null
  journal: string
  doi: string | null
  pmid: string | null
  keywords: string[]
  publication_type: string
  language: string
  my_decision: DecisionInfo | null
}

export interface Progress {
  phase: Phase
  eligible: number
  included: number
  excluded: number
  conflicts: number
  pending: number
  reviewers_required: number
  blind: boolean
  remaining_for_me: number
  reviewers: {
    user_id: string
    full_name: string
    decided: number
    included: number
    excluded: number
    maybe: number
  }[]
}

export interface ConflictItem {
  record: ScreeningItem
  decisions: DecisionInfo[]
}

export interface ScreenedItem {
  record: ScreeningItem
  state: 'pending' | 'included' | 'excluded' | 'conflict' | 'hidden'
  decisions: DecisionInfo[]
}

export interface PairAgreement {
  user_a: string
  user_b: string
  n: number
  percent: number | null
  kappa: number | null
}
export interface Prisma {
  identification: { by_source: { source: string; records: number }[]; total: number; duplicates_removed: number }
  screening: { screened: number; excluded: number; pending: number }
  retrieval: { sought: number; not_retrieved: number }
  eligibility: {
    assessed: number
    excluded: number
    reasons: { reason: string | null; count: number }[]
    pending: number
  }
  included: number
}
export type ProviderKind = 'ollama' | 'openai' | 'anthropic' | 'google' | 'openrouter' | 'custom'
export interface Provider {
  id: string
  name: string
  kind: ProviderKind
  base_url: string
  api_key_hint: string
  is_local: boolean
}
export interface TaskModel {
  provider_id: string | null
  model: string
  price_input: number
  price_output: number
}
export interface InstanceAISettings {
  screening: TaskModel
  embeddings: TaskModel
}
export interface ProjectAISettings {
  enabled: boolean
  local_only: boolean
  mode: 'suggest' | 'second_reviewer'
  budget_usd: number | null
  extra_instructions: string
  active_learning: boolean
  stop_after_irrelevant: number
}
export type AIScope = 'pending' | 'excluded' | 'calibration'
export interface AIEstimate {
  records: number
  cached: number
  input_tokens: number
  output_tokens: number
  cost_usd: number
  local: boolean
  budget_usd: number | null
  spent_usd: number
}
export interface AISuggestion {
  record_id: string
  decision: DecisionKind
  confidence: number | null
  justification: string
  criteria: { criterion: string; status: 'met' | 'violated' | 'unclear' }[]
  model_key: string
  created_at: string
}
export interface AICalibration {
  n: number
  tp: number
  fp: number
  tn: number
  fn: number
  maybe: number
  sensitivity: number | null
  specificity: number | null
  kappa: number | null
}
export interface AIUsage {
  spent_usd: number
  input_tokens: number
  output_tokens: number
  calls: number
}
export interface AIFlag {
  record: ScreeningItem
  suggestion: AISuggestion
}
export interface AICurve {
  total: number
  screened: number
  found: number
  since_last_include: number
  expected_remaining: number | null
  stop_after_irrelevant: number
  should_stop: boolean
  prioritized: boolean
  points: { screened: number; found: number }[]
}
export interface RecordFile {
  id: string
  record_id: string
  filename: string
  size: number
  pages: number
  source: 'upload' | 'zip' | 'open_access'
  source_url: string
  is_main: boolean
  has_text: boolean
  created_at: string
}
export interface FilesSummary {
  records: number
  with_pdf: number
  without_text: number
  from_open_access: number
}
