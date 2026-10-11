import type { GradeDomainKey, GradeRowT } from '../api/types'

export const DOWN_DOMAINS: GradeDomainKey[] = [
  'risk_of_bias',
  'inconsistency',
  'indirectness',
  'imprecision',
  'publication_bias',
]
export const UP_DOMAINS: GradeDomainKey[] = ['large_effect', 'dose_response', 'confounding']

const LEVELS = ['very_low', 'low', 'moderate', 'high'] as const
export type Certainty = (typeof LEVELS)[number]

/** Mesma regra do servidor: começa em 4 (ECR) ou 2 (observacional), rebaixa e eleva, limita a 1–4. */
export function certaintyOf(row: Pick<GradeRowT, 'design' | 'domains'>): Certainty {
  let score = row.design === 'rct' ? 4 : 2
  for (const k of DOWN_DOMAINS) score += Math.min(0, row.domains[k]?.rating ?? 0)
  for (const k of UP_DOMAINS) score += Math.max(0, row.domains[k]?.rating ?? 0)
  return LEVELS[Math.max(1, Math.min(4, score)) - 1]
}

/** ⊕⊕⊕◯ para "moderada". */
export function certaintySymbols(c: Certainty): string {
  const n = LEVELS.indexOf(c) + 1
  return '⊕'.repeat(n) + '◯'.repeat(4 - n)
}

/** Sugestão → domínio a que ela se refere. */
export const SUGGESTION_DOMAIN: Record<string, GradeDomainKey> = {
  inconsistency_high: 'inconsistency',
  inconsistency_moderate: 'inconsistency',
  imprecision_crosses_null: 'imprecision',
  imprecision_small_sample: 'imprecision',
  publication_bias_few_studies: 'publication_bias',
  publication_bias_egger: 'publication_bias',
}

export function csvCell(v: string | number | null | undefined): string {
  const s = v == null ? '' : String(v)
  return /[";\n\r,]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
}
