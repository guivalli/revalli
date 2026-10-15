import type { SearchOperator, SearchRow } from '../api/types'

export const emptyRow = (op: SearchOperator = 'AND'): SearchRow => ({ op, field: 'title_abstract', term: '' })
