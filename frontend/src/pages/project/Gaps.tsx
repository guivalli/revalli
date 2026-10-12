import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router-dom'
import { gapExportUrl, useGapDimensions, useGapMap } from '../../api/gaps'
import type { GapMap } from '../../api/types'
import { SynthesisNav } from '../../components/SynthesisNav'
import { Card, ErrorText, Field, Select } from '../../components/ui'
import { useProjectContext } from './context'

const NONE = '__none__'

function Axis({
  value,
  onChange,
  dims,
}: {
  value: string
  onChange: (v: string) => void
  dims: { codes: { ref: string; label: string }[]; fields: { ref: string; label: string }[] }
}) {
  const { t } = useTranslation()
  return (
    <Select value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">{t('gaps.choose')}</option>
      {dims.codes.length > 0 && (
        <optgroup label={t('gaps.from_codes')}>
          {dims.codes.map((d) => (
            <option key={d.ref} value={d.ref}>
              {d.label}
            </option>
          ))}
        </optgroup>
      )}
      {dims.fields.length > 0 && (
        <optgroup label={t('gaps.from_fields')}>
          {dims.fields.map((d) => (
            <option key={d.ref} value={d.ref}>
              {d.label}
            </option>
          ))}
        </optgroup>
      )}
    </Select>
  )
}

function Matrix({ map, pid }: { map: GapMap; pid: string }) {
  const { t } = useTranslation()
  const [open, setOpen] = useState<{ row: string; col: string } | null>(null)
  const cells = new Map(map.cells.map((c) => [`${c.row}|${c.col}`, c.studies]))
  const max = Math.max(1, ...map.cells.map((c) => c.studies.length))
  const label = (k: string, l: string) => (k === NONE ? t('gaps.unclassified') : l)
  const shown = open ? (cells.get(`${open.row}|${open.col}`) ?? []) : []
  const rowLabel = map.rows.categories.find((c) => c.key === open?.row)
  const colLabel = map.cols.categories.find((c) => c.key === open?.col)

  return (
    <div className="space-y-4">
      <div className="overflow-x-auto">
        <table className="border-separate border-spacing-1 text-sm">
          <thead>
            <tr>
              <th className="p-2 text-left align-bottom text-xs font-normal text-stone-500">
                {map.rows.title} ↓ · {map.cols.title} →
              </th>
              {map.cols.categories.map((c) => (
                <th key={c.key} className="min-w-24 p-2 text-center align-bottom font-medium">
                  {label(c.key, c.label)}
                  <span className="block text-xs font-normal text-stone-500">n = {c.n}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {map.rows.categories.map((r) => (
              <tr key={r.key}>
                <th scope="row" className="p-2 text-left font-medium">
                  {label(r.key, r.label)}
                  <span className="block text-xs font-normal text-stone-500">n = {r.n}</span>
                </th>
                {map.cols.categories.map((c) => {
                  const n = cells.get(`${r.key}|${c.key}`)?.length ?? 0
                  const active = open?.row === r.key && open?.col === c.key
                  return (
                    <td key={c.key} className="p-0">
                      <button
                        type="button"
                        disabled={n === 0}
                        aria-label={`${label(r.key, r.label)} × ${label(c.key, c.label)}: ${n}`}
                        onClick={() => setOpen(active ? null : { row: r.key, col: c.key })}
                        className={`h-12 w-full rounded-md border text-center tabular-nums ${
                          n === 0
                            ? 'border-dashed border-stone-300 text-stone-400 dark:border-stone-700'
                            : 'border-transparent font-semibold text-white'
                        } ${active ? 'ring-2 ring-brand-500 ring-offset-1' : ''}`}
                        style={
                          n > 0
                            ? { background: `rgb(13 148 136 / ${0.35 + 0.65 * (n / max)})` }
                            : undefined
                        }
                      >
                        {n === 0 ? '·' : n}
                      </button>
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-stone-500">{t('gaps.legend')}</p>
      {open && rowLabel && colLabel && (
        <Card className="space-y-2">
          <p className="text-sm font-medium">
            {label(rowLabel.key, rowLabel.label)} × {label(colLabel.key, colLabel.label)}
          </p>
          <ul className="space-y-1 text-sm">
            {shown.map((id) => {
              const s = map.studies[id]
              return (
                <li key={id}>
                  <Link className="text-brand-600 dark:text-brand-300 hover:underline" to={`/projetos/${pid}/sintese/${id}`}>
                    {s.label}
                  </Link>
                  <span className="text-stone-500">
                    {' '}
                    · {s.title}
                    {s.year ? ` (${s.year})` : ''}
                  </span>
                </li>
              )
            })}
          </ul>
        </Card>
      )}
    </div>
  )
}

export default function Gaps() {
  const { t } = useTranslation()
  const { project } = useProjectContext()
  const [params, setParams] = useSearchParams()
  const rows = params.get('rows') ?? ''
  const cols = params.get('cols') ?? ''
  const dims = useGapDimensions(project.id)
  const map = useGapMap(project.id, rows, cols)
  const set = (key: 'rows' | 'cols', value: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next, { replace: true })
  }
  const none = dims.data && dims.data.codes.length === 0 && dims.data.fields.length === 0

  return (
    <div className="space-y-6">
      <SynthesisNav pid={project.id} />
      <Card className="space-y-4">
        <div>
          <h2 className="font-semibold">{t('gaps.title')}</h2>
          <p className="text-sm text-stone-500">{t('gaps.hint')}</p>
        </div>
        {none && <p className="text-sm text-amber-700 dark:text-amber-300">{t('gaps.no_dimensions')}</p>}
        {dims.data && !none && (
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('gaps.rows')}>
              <Axis value={rows} onChange={(v) => set('rows', v)} dims={dims.data} />
            </Field>
            <Field label={t('gaps.cols')}>
              <Axis value={cols} onChange={(v) => set('cols', v)} dims={dims.data} />
            </Field>
          </div>
        )}
        <ErrorText error={dims.error ?? map.error} />
      </Card>
      {map.data && (
        <Card className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm text-stone-500">
              {t('gaps.studies', { count: map.data.total_studies })}
            </p>
            <a
              className="text-sm text-brand-600 dark:text-brand-300 hover:underline"
              href={gapExportUrl(project.id, rows, cols)}
            >
              {t('gaps.export')}
            </a>
          </div>
          <Matrix key={`${rows}|${cols}`} map={map.data} pid={project.id} />
        </Card>
      )}
    </div>
  )
}
