import type { RecordItem } from '../api/types'

export function citationLine(r: RecordItem): string {
  const authors =
    r.authors.length > 3 ? `${r.authors.slice(0, 3).join('; ')} et al.` : r.authors.join('; ')
  const parts = [authors, r.year ? String(r.year) : '', r.journal].filter(Boolean)
  return parts.join(' · ')
}
