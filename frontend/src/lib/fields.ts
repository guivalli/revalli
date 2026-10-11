import { useTranslation } from 'react-i18next'
import type { FieldDef, FieldValue } from '../api/types'

type Row = Record<string, string | number | null>

export type Values = Record<string, FieldValue>

export const SIGNALS = ['Y', 'PY', 'PN', 'N', 'NI']

/** Mesma regra do servidor: todas as condições do campo precisam valer. */
export function isVisible(f: FieldDef, values: Values) {
  return (f.show_if ?? []).every((c) => c.values.includes(String(values[c.field] ?? '')))
}

/** Rótulo de uma opção: sinalizadoras e julgamentos têm tradução; o resto vem do formulário. */
export function useOptionLabel() {
  const { t } = useTranslation()
  return (f: Pick<FieldDef, 'type'>, o: string) =>
    f.type === 'signal' ? t(`rob.signal_${o}`) : f.type === 'judgement' ? t(`rob.level_${o}`) : o
}

export function useFormatValue() {
  const { t } = useTranslation()
  const optionLabel = useOptionLabel()
  return (f: FieldDef, v: FieldValue | undefined): string => {
    if (v === null || v === undefined || v === '') return '–'
    if (typeof v === 'boolean') return v ? t('extraction.yes') : t('extraction.no')
    if (f.type === 'table' && Array.isArray(v))
      return (v as Row[])
        .map((row) => f.columns.map((c) => row[c.id] ?? '–').join(' · '))
        .join(' | ')
    if (Array.isArray(v)) return (v as string[]).map((o) => optionLabel(f, o)).join('; ')
    if (typeof v === 'number') return v.toLocaleString()
    return f.options.length ? optionLabel(f, String(v)) : String(v)
  }
}


/** Identificador estável do campo, usado nas colunas da exportação. */
export function slugify(text: string, taken: Set<string>, fallback = 'campo') {
  let base = text
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 36)
  if (!/^[a-z]/.test(base)) base = `${fallback}_${base}`.replace(/_+$/, '')
  let id = base
  for (let i = 2; taken.has(id); i++) id = `${base}_${i}`
  return id
}

