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
  method: SearchMethod
  created_at: string
}

export type SearchMethod = 'database' | 'citation_backward' | 'citation_forward'


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
  citation: { direction: 'backward' | 'forward'; seeds: string[] } | null
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
  kind: 'dedup' | 'enrich' | 'ai_screen' | 'ai_embed' | 'ai_criteria' | 'ai_tags' | 'ai_reasons' | 'pdf_zip' | 'pdf_oa' | 'ai_extract' | 'api_search' | 'snowball' | 'corpus_index' | 'watch_run'
  status: 'queued' | 'running' | 'done' | 'failed' | 'cancelling' | 'cancelled'
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

export interface CriterionItem {
  kind: 'include' | 'exclude'
  name: string
  definition: string
  examples: string[]
}

export interface TagItem {
  name: string
  description: string
}

export interface ScreeningSettings {
  blind: boolean
  reviewers_title_abstract: number
  reviewers_full_text: number
  inclusion_criteria: string
  exclusion_criteria: string
  highlight_include: string[]
  highlight_exclude: string[]
  criteria_items: CriterionItem[]
  tag_vocabulary: TagItem[]
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
  identification: {
    by_source: SourceCount[]
    other_methods: SourceCount[]
    total: number
    duplicates_removed: number
  }
  screening: { screened: number; excluded: number; pending: number }
  retrieval: { sought: number; not_retrieved: number }
  eligibility: {
    assessed: number
    excluded: number
    reasons: { reason: string | null; count: number }[]
    pending: number
  }
  included: number
  included_reports: number
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
  extraction: TaskModel
  chat: TaskModel
}
export interface ProjectAISettings {
  enabled: boolean
  local_only: boolean
  mode: 'suggest' | 'second_reviewer'
  budget_usd: number | null
  extra_instructions: string
  active_learning: boolean
  stop_after_irrelevant: number
  suggest_tags: boolean
  suggest_reasons: boolean
  reveal_suggestions: 'after' | 'before'
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
  tags: string[]
  exclusion_reason: string
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
export interface PendingFile {
  record_id: string
  title: string
  authors: string[]
  year: number | null
  journal: string
  doi: string | null
  pmid: string | null
  url: string
  link: string
  proxy_link: string
}

export interface FilesSummary {
  records: number
  with_pdf: number
  without_text: number
  from_open_access: number
}

export interface StudyRecord {
  id: string
  title: string
  authors: string[]
  year: number | null
  doi: string | null
  is_primary: boolean
  state: 'pending' | 'included' | 'excluded' | 'conflict' | null
}

export interface Study {
  id: string
  label: string
  reports: StudyRecord[]
}

export interface StudySuggestion {
  key: string
  records: StudyRecord[]
}

export interface StudyCandidate {
  id: string
  title: string
  authors: string[]
  year: number | null
  study_id: string | null
}

// --- Extração de dados ---------------------------------------------------------------

export type FieldType =
  | 'section'
  | 'text'
  | 'long_text'
  | 'number'
  | 'integer'
  | 'choice'
  | 'multi'
  | 'boolean'
  | 'table'
  | 'signal'
  | 'judgement'

export interface ColumnDef {
  id: string
  label: string
  type: 'text' | 'number' | 'integer'
}

export interface FieldDef {
  id: string
  label: string
  type: FieldType
  help: string
  required: boolean
  options: string[]
  columns: ColumnDef[]
  rows: string[]
  ai: boolean
  ai_hint: string
  domain: string
  algorithm: string
  show_if: { field: string; values: string[] }[]
}

export interface ExtractionFormT {
  id: string
  name: string
  kind: 'extraction' | 'rob'
  template: string
  fields: FieldDef[]
  version: number
  extractors: number
  created_at: string
}

export type FieldValue = string | number | boolean | string[] | Record<string, string | number | null>[] | null

export interface QuoteT {
  text: string
  page: number | null
  file_id: string | null
  score: number | null
  verified: boolean
}

export interface ExtractionT {
  id: string
  kind: 'reviewer' | 'ai' | 'consensus'
  user_id: string | null
  user_name: string
  values: Record<string, FieldValue>
  quotes: Record<string, QuoteT>
  status: 'draft' | 'done'
  form_version: number
  updated_at: string
  suggested: Record<string, string>
}

export type UnitState = 'pending' | 'in_progress' | 'complete' | 'conflict' | 'agreed' | 'resolved'

export interface UnitT {
  record_id: string
  report_ids: string[]
  label: string
  title: string
  year: number | null
  done: number
  mine: 'draft' | 'done' | null
  has_ai: boolean
  consensus: boolean
  state: UnitState
}

export interface UnitDetailT {
  unit: UnitT
  files: RecordFile[]
  form: ExtractionFormT
  mine: ExtractionT | null
  ai: ExtractionT | null
  others: ExtractionT[]
  consensus: ExtractionT | null
  can_see_others: boolean
  can_resolve: boolean
}

export interface ComparisonT {
  extractions: ExtractionT[]
  fields: { field_id: string; values: Record<string, FieldValue>; agree: boolean }[]
  agreed_values: Record<string, FieldValue>
}

export interface RobSummaryT {
  domains: { id: string; domain: string; label: string }[]
  scale: string[]
  rows: { record_id: string; label: string; judgements: Record<string, string | null> }[]
}

export interface SourceCount {
  source: string
  method: SearchMethod
  records: number
}

export type ApiSource = 'pubmed' | 'openalex' | 'europepmc' | 'scielo' | 'pepsic'

export interface SourcePreview {
  count: number
  max: number
  translation: string
  warnings: string[]
  sample: {
    title: string
    authors: string[]
    year: number | null
    journal: string
    doi: string | null
    pmid: string | null
  }[]
}

export interface Translation {
  query: string
  notes: string[]
  model: string
}

export interface Code {
  id: string
  parent_id: string | null
  name: string
  description: string
  color: string
  position: number
  excerpts: number
}

export interface Excerpt {
  id: string
  record_id: string
  study: string
  file_id: string | null
  file_record_id: string | null
  page: number | null
  text: string
  note: string
  code_ids: string[]
  user_id: string | null
  user_name: string
  created_at: string
}

export interface CodingUnit {
  record_id: string
  label: string
  report_ids: string[]
  title: string
  year: number | null
  excerpts: number
  has_pdf: boolean
}

export type ChecklistStatus = 'pending' | 'done' | 'na'

export interface ChecklistEntry {
  item: string
  status: ChecklistStatus
  location: string
  note: string
  updated_at: string | null
}

export interface ChecklistFacts {
  review_type: string
  searches: {
    source: string
    method: SearchMethod
    searched_on: string | null
    has_query: boolean
    via_api: boolean
    reported: number | null
    imported: number
  }[]
  screening: { reviewers_title_abstract: number; reviewers_full_text: number; blind: boolean; has_criteria: boolean }
  ai: { enabled: boolean; mode: 'suggest' | 'second_reviewer'; local_only: boolean; calls: Record<string, number> }
  forms: { name: string; kind: 'extraction' | 'rob'; template: string; extractors: number }[]
  coding: { codes: number; excerpts: number }
  prisma: Prisma
}

export type Measure = 'MD' | 'SMD' | 'RR' | 'OR' | 'RD' | 'HR' | 'GENERIC'

export interface MetaRow {
  id: string
  record_id: string | null
  label: string
  subgroup: string
  n1?: number | null
  mean1?: number | null
  sd1?: number | null
  e1?: number | null
  n2?: number | null
  mean2?: number | null
  sd2?: number | null
  e2?: number | null
  hr?: number | null
  hr_lower?: number | null
  hr_upper?: number | null
  yi?: number | null
  sei?: number | null
}

export interface MetaAnalysisT {
  id: string
  name: string
  outcome: string
  measure: Measure
  model: 'random' | 'fixed'
  label1: string
  label2: string
  lower_favours_1: boolean
  rows: MetaRow[]
}

export interface PooledT {
  k: number
  estimate: number
  lower: number
  upper: number
  p: number
  z: number
  q: number
  df: number
  p_q: number | null
  i2: number
  tau2: number
  prediction: [number, number] | null
  participants: number | null
}

export interface MetaResult {
  measure: Measure
  model: string
  log_scale: boolean
  studies: {
    id: string
    label: string
    subgroup: string
    yi: number | null
    se: number | null
    estimate: number | null
    lower: number | null
    upper: number | null
    weight: number | null
    skipped: string | null
    corrected: boolean
    participants: number | null
  }[]
  pooled: PooledT | null
  subgroups: { name: string; pooled: PooledT | null }[]
  subgroup_test: { q: number; df: number; p: number } | null
  egger: { intercept: number; se: number; t: number; p: number } | null
}

export type GradeDomainKey =
  | 'risk_of_bias'
  | 'inconsistency'
  | 'indirectness'
  | 'imprecision'
  | 'publication_bias'
  | 'large_effect'
  | 'dose_response'
  | 'confounding'

export interface GradeRowT {
  id: string
  outcome: string
  analysis_id: string | null
  design: 'rct' | 'observational'
  studies: number | null
  participants: number | null
  effect: string
  domains: Partial<Record<GradeDomainKey, { rating: number; reason: string }>>
  importance: 'critical' | 'important' | 'limited'
  comments: string
  certainty: 'high' | 'moderate' | 'low' | 'very_low'
  auto: {
    measure: Measure
    k: number
    participants: number | null
    estimate: number
    lower: number
    upper: number
    i2: number
    crosses_null: boolean
    egger_p: number | null
  } | null
  suggestions: string[]
}

export interface CorpusStatus {
  chunks: number
  pending_files: number
  embedded: number
  embeddings_model: string | null
  chat_model: string | null
  enabled: boolean
}

export interface CorpusSource {
  n: number
  record_id: string
  file_id: string
  page: number
  title: string
  authors: string[]
  year: number | null
  excerpt: string
  quote: string
  score: number
  verified: boolean
}

export interface CorpusMessage {
  id: string
  question: string
  answer: string
  sources: CorpusSource[]
  grounded: boolean
  answerable: boolean
  unsupported_numbers: string[]
  scope: 'included' | 'all'
  model: string
  created_at: string
}

export interface ApiTokenInfo {
  id: string
  name: string
  prefix: string
  project_id: string | null
  scope: string
  created_at: string
  expires_at: string | null
  last_used_at: string | null
}

export interface ApiTokenCreated extends ApiTokenInfo {
  token: string
}

export interface Watch {
  id: string
  kind: 'api_search' | 'feed_url'
  name: string
  source: string
  query: string
  url: string
  has_secret: boolean
  every_days: number
  enabled: boolean
  next_run_at: string | null
  last_run_at: string | null
  last_status: '' | 'ok' | 'error'
  last_error: string
  last_new: number
  last_found: number
  total_new: number
}

export interface WatchInput {
  kind: 'api_search' | 'feed_url'
  name: string
  source: string
  query: string
  url: string
  secret: string
  clear_secret: boolean
  every_days: number
  enabled: boolean
}

export interface GapDimensions {
  codes: { ref: string; label: string; categories: number }[]
  fields: { ref: string; label: string; categories: number }[]
}

export interface GapAxis {
  source: string
  title: string
  categories: { key: string; label: string; n: number }[]
}

export interface GapMap {
  rows: GapAxis
  cols: GapAxis
  cells: { row: string; col: string; studies: string[] }[]
  studies: Record<string, { label: string; title: string; year: number | null }>
  total_studies: number
}

export interface CriteriaDraft {
  summary: string
  items: CriterionItem[]
  questions: string[]
}

export interface TagProposals {
  tags: TagItem[]
  sampled: number
}

export interface ReasonGroup {
  label: string
  existing: boolean
  members: string[]
  count: number
}

export interface ReasonGroups {
  groups: ReasonGroup[]
  total: number
}

export interface AssistStrategy {
  base: string
  query: string
  notes: string[]
}

export interface AssistTurn {
  role: 'user' | 'assistant'
  content: string
  strategies?: AssistStrategy[]
  model?: string
}

export interface AssistReply {
  reply: string
  strategies: AssistStrategy[]
  model: string
}

export interface OllamaState {
  configured: boolean
  reachable: boolean
  active: boolean
  state: string
  enabled: boolean
  error: string | null
}

export interface SourcesSettings {
  openalex_key_set: boolean
  openalex_key_hint: string
  openalex_key_source: 'ui' | 'env' | 'none'
  institution_proxy: string
}
