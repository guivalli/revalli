import { useTranslation } from 'react-i18next'
import type { FieldDef, FieldValue } from '../api/types'
import { useOptionLabel } from '../lib/fields'
import { Input, Select } from './ui'

type Row = Record<string, string | number | null>

function TableInput({
  f,
  value,
  onChange,
  disabled,
}: {
  f: FieldDef
  value: Row[]
  onChange: (v: Row[] | null) => void
  disabled?: boolean
}) {
  const { t } = useTranslation()
  const fixed = f.rows.length > 0
  const rows: Row[] = fixed
    ? f.rows.map((label, i) => value[i] ?? { [f.columns[0].id]: label })
    : value.length
      ? value
      : [{}]
  const set = (i: number, col: string, v: string) => {
    const next = rows.map((r, j) => (j === i ? { ...r, [col]: v === '' ? null : v } : r))
    onChange(next)
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs text-stone-500">
            {f.columns.map((c) => (
              <th key={c.id} className="px-1 pb-1 font-medium">
                {c.label}
              </th>
            ))}
            {!fixed && <th />}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {f.columns.map((c) => (
                <td key={c.id} className="p-1">
                  <Input
                    aria-label={`${c.label} ${i + 1}`}
                    inputMode={c.type === 'text' ? undefined : 'decimal'}
                    value={row[c.id] ?? ''}
                    disabled={disabled}
                    onChange={(e) => set(i, c.id, e.target.value)}
                  />
                </td>
              ))}
              {!fixed && (
                <td className="w-8">
                  <button
                    type="button"
                    aria-label={t('extraction.remove_row')}
                    className="px-1 text-stone-400 hover:text-red-600 disabled:opacity-40"
                    disabled={disabled}
                    onClick={() => onChange(rows.filter((_, j) => j !== i))}
                  >
                    ×
                  </button>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
      {!fixed && !disabled && (
        <button
          type="button"
          className="mt-1 text-sm text-brand-600 dark:text-brand-300 hover:underline"
          onClick={() => onChange([...rows, {}])}
        >
          {t('extraction.add_row')}
        </button>
      )}
    </div>
  )
}

export function FieldInput({
  f,
  value,
  onChange,
  suggested,
  disabled,
}: {
  f: FieldDef
  value: FieldValue | undefined
  onChange: (v: FieldValue) => void
  suggested?: string
  disabled?: boolean
}) {
  const { t } = useTranslation()
  const optionLabel = useOptionLabel()
  const id = `f-${f.id}`
  switch (f.type) {
    case 'long_text':
      return (
        <textarea
          id={id}
          rows={3}
          disabled={disabled}
          className="w-full rounded-md border border-stone-300 bg-white px-3 py-2 text-sm dark:border-stone-700 dark:bg-stone-900"
          value={(value as string) ?? ''}
          onChange={(e) => onChange(e.target.value)}
        />
      )
    case 'text':
      return <Input id={id} disabled={disabled} value={(value as string) ?? ''} onChange={(e) => onChange(e.target.value)} />
    case 'number':
    case 'integer':
      return (
        <Input
          id={id}
          inputMode="decimal"
          className="max-w-48"
          disabled={disabled}
          value={value === null || value === undefined ? '' : String(value)}
          onChange={(e) => onChange(e.target.value)}
        />
      )
    case 'boolean':
      return (
        <Select
          id={id}
          className="max-w-48"
          disabled={disabled}
          value={value === true ? 'true' : value === false ? 'false' : ''}
          onChange={(e) => onChange(e.target.value === '' ? null : e.target.value === 'true')}
        >
          <option value="">–</option>
          <option value="true">{t('extraction.yes')}</option>
          <option value="false">{t('extraction.no')}</option>
        </Select>
      )
    case 'choice':
    case 'judgement':
      return (
        <div className="flex flex-wrap items-center gap-2">
          <Select
            id={id}
            className="max-w-sm"
            disabled={disabled}
            value={(value as string) ?? ''}
            onChange={(e) => onChange(e.target.value || null)}
          >
            <option value="">{f.type === 'judgement' && suggested ? t('extraction.use_suggested') : '–'}</option>
            {f.options.map((o) => (
              <option key={o} value={o}>
                {optionLabel(f, o)}
              </option>
            ))}
          </Select>
          {f.type === 'judgement' && suggested && (
            <span className="text-sm text-stone-500">
              {t('extraction.suggested', { value: optionLabel(f, suggested) })}
            </span>
          )}
        </div>
      )
    case 'signal':
      return (
        <div role="radiogroup" aria-labelledby={`${id}-label`} className="flex flex-wrap gap-1">
          {f.options.map((o) => (
            <label
              key={o}
              title={optionLabel(f, o)}
              className={`cursor-pointer rounded-md border px-2.5 py-1 text-sm ${
                value === o
                  ? 'border-brand-600 bg-brand-600 text-white'
                  : 'border-stone-300 hover:bg-stone-100 dark:border-stone-700 dark:hover:bg-stone-800'
              }`}
            >
              <input
                type="radio"
                name={id}
                className="sr-only"
                checked={value === o}
                disabled={disabled}
                onChange={() => onChange(o)}
                onClick={() => value === o && onChange(null)}
              />
              {o}
            </label>
          ))}
        </div>
      )
    case 'multi': {
      const list = (value as string[] | null) ?? []
      return (
        <div className="flex flex-wrap gap-x-4 gap-y-1">
          {f.options.map((o) => (
            <label key={o} className="flex items-center gap-1.5 text-sm">
              <input
                type="checkbox"
                disabled={disabled}
                checked={list.includes(o)}
                onChange={(e) => onChange(e.target.checked ? [...list, o] : list.filter((x) => x !== o))}
              />
              {o}
            </label>
          ))}
        </div>
      )
    }
    case 'table':
      return (
        <TableInput
          f={f}
          value={(value as Row[] | null) ?? []}
          disabled={disabled}
          onChange={(v) => onChange(v)}
        />
      )
    default:
      return null
  }
}
