import { useTranslation } from 'react-i18next'
import type { SearchField, SearchOperator, SearchRow, SourceFields } from '../api/types'
import { emptyRow } from './searchRows'
import { Button, Input, Select } from './ui'

/** Construtor de busca no estilo da busca avançada das bases: uma linha por conceito, com o
 * operador, o termo e o campo. Só oferece os campos que a base aceita. */
export function SearchBuilder({
  rows,
  onChange,
  info,
}: {
  rows: SearchRow[]
  onChange: (rows: SearchRow[]) => void
  info: SourceFields | undefined
}) {
  const { t } = useTranslation()
  const fields: SearchField[] = info?.fields ?? ['title_abstract']
  const set = (i: number, patch: Partial<SearchRow>) =>
    onChange(rows.map((r, j) => (j === i ? { ...r, ...patch } : r)))
  return (
    <div className="space-y-2">
      {rows.map((row, i) => (
        <div key={i} className="grid gap-2 sm:grid-cols-[6rem_1fr_13rem_auto]">
          {i === 0 ? (
            <span aria-hidden className="hidden sm:block" />
          ) : (
            <Select
              aria-label={t('sources.row_op')}
              value={row.op}
              onChange={(e) => set(i, { op: e.target.value as SearchOperator })}
            >
              {(['AND', 'OR', 'NOT'] as const).map((op) => (
                <option key={op} value={op}>
                  {t(`sources.op_${op}`)}
                </option>
              ))}
            </Select>
          )}
          <Input
            aria-label={t('sources.row_term')}
            placeholder={t(`sources.placeholder_${row.field}`, { defaultValue: t('sources.placeholder_default') })}
            value={row.term}
            onChange={(e) => set(i, { term: e.target.value })}
          />
          <Select
            aria-label={t('sources.row_field')}
            value={fields.includes(row.field) ? row.field : 'title_abstract'}
            onChange={(e) => set(i, { field: e.target.value as SearchField })}
          >
            {fields.map((f) => (
              <option key={f} value={f}>
                {t(`sources.field_${f}`)}
              </option>
            ))}
          </Select>
          <Button
            type="button"
            variant="ghost"
            aria-label={t('sources.row_remove')}
            disabled={rows.length === 1}
            onClick={() => onChange(rows.filter((_, j) => j !== i))}
          >
            ✕
          </Button>
        </div>
      ))}
      <div className="flex flex-wrap items-center gap-3">
        <Button
          type="button"
          variant="ghost"
          className="border border-stone-300 dark:border-stone-700"
          onClick={() => onChange([...rows, emptyRow()])}
        >
          + {t('sources.row_add')}
        </Button>
        {info && !info.or_across_fields && (
          <span className="text-xs text-stone-500">{t('sources.or_hint')}</span>
        )}
      </div>
    </div>
  )
}
