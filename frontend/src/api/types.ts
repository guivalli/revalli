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
