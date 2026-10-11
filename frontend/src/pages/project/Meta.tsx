import { useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router-dom'
import { metaExportUrl, useAnalyses, useMetaActions, useMetaResult, type AnalysisPayload } from '../../api/meta'
import { useCodingUnits } from '../../api/synthesis'
import type { Measure, MetaAnalysisT, MetaRow } from '../../api/types'
import { ForestPlot, FunnelPlot } from '../../components/MetaPlots'
import { SynthesisNav } from '../../components/SynthesisNav'
import { Button, Card, ErrorText, Field, Input, Select } from '../../components/ui'
import { savePng, saveSvg } from '../../lib/download'
import { useFmt, useFmtP } from '../../lib/format'
import { useProjectContext } from './context'

const MEASURES: Measure[] = ['RR', 'OR', 'RD', 'MD', 'SMD', 'HR', 'GENERIC']
type NumKey = Exclude<keyof MetaRow, 'id' | 'record_id' | 'label' | 'subgroup'>

const COLUMNS: Record<Measure, NumKey[]> = {
  RR: ['e1', 'n1', 'e2', 'n2'],
  OR: ['e1', 'n1', 'e2', 'n2'],
  RD: ['e1', 'n1', 'e2', 'n2'],
  MD: ['n1', 'mean1', 'sd1', 'n2', 'mean2', 'sd2'],
  SMD: ['n1', 'mean1', 'sd1', 'n2', 'mean2', 'sd2'],
  HR: ['hr', 'hr_lower', 'hr_upper'],
  GENERIC: ['yi', 'sei'],
}

const newId = () => Math.random().toString(36).slice(2, 10)

function parseNum(v: string): number | null {
  const s = v.trim().replace(/\s/g, '').replace(',', '.')
  if (!s) return null
  const n = Number(s)
  return Number.isFinite(n) ? n : null
}

const blank = (): AnalysisPayload => ({
  name: '',
  outcome: '',
  measure: 'RR',
  model: 'random',
  label1: '',
  label2: '',
  lower_favours_1: true,
  rows: [],
})

function Editor({ initial, onSaved }: { initial: MetaAnalysisT | null; onSaved: (id: string) => void }) {
  const { t } = useTranslation()
  const { project, canManage } = useProjectContext()
  const { create, update, remove } = useMetaActions(project.id)
  const units = useCodingUnits(project.id)
  const [a, setA] = useState<AnalysisPayload>(() => (initial ? { ...initial } : blank()))
  const [text, setText] = useState<Record<string, string>>({})
  const [paste, setPaste] = useState('')
  const cols = COLUMNS[a.measure]
  const mut = initial ? update : create
  const setRow = (i: number, patch: Partial<MetaRow>) =>
    setA({ ...a, rows: a.rows.map((r, j) => (j === i ? { ...r, ...patch } : r)) })
  const cellText = (r: MetaRow, c: NumKey) => text[`${r.id}:${c}`] ?? (r[c] == null ? '' : String(r[c]).replace('.', t('meta.decimal')))

  const addIncluded = () => {
    const have = new Set(a.rows.map((r) => r.record_id))
    const extra = (units.data ?? [])
      .filter((u) => !have.has(u.record_id))
      .map((u) => ({ id: newId(), record_id: u.record_id, label: u.label, subgroup: '' }))
    setA({ ...a, rows: [...a.rows, ...extra] })
  }
  const applyPaste = () => {
    const rows = paste
      .split(/\r?\n/)
      .map((l) => l.split('\t'))
      .filter((c) => c[0]?.trim())
      .map((c) => {
        const row: MetaRow = { id: newId(), record_id: null, label: c[0].trim(), subgroup: (c[cols.length + 1] ?? '').trim() }
        cols.forEach((k, i) => (row[k] = parseNum(c[i + 1] ?? '')))
        return row
      })
    setA({ ...a, rows: [...a.rows, ...rows] })
    setPaste('')
  }
  const save = () => {
    const done = { onSuccess: (saved: MetaAnalysisT) => onSaved(saved.id) }
    if (initial) update.mutate({ id: initial.id, body: a }, done)
    else create.mutate(a, done)
  }

  return (
    <Card className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Field label={t('meta.name')}>
          <Input value={a.name} disabled={!canManage} onChange={(e) => setA({ ...a, name: e.target.value })} />
        </Field>
        <Field label={t('meta.measure')}>
          <Select value={a.measure} disabled={!canManage} onChange={(e) => setA({ ...a, measure: e.target.value as Measure })}>
            {MEASURES.map((m) => (
              <option key={m} value={m}>
                {t(`meta.measure_${m}`)}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={t('meta.model')}>
          <Select value={a.model} disabled={!canManage} onChange={(e) => setA({ ...a, model: e.target.value as 'random' | 'fixed' })}>
            <option value="random">{t('meta.model_random')}</option>
            <option value="fixed">{t('meta.model_fixed')}</option>
          </Select>
        </Field>
        <Field label={t('meta.outcome')}>
          <Input value={a.outcome} disabled={!canManage} onChange={(e) => setA({ ...a, outcome: e.target.value })} />
        </Field>
        <Field label={t('meta.group1')}>
          <Input value={a.label1} disabled={!canManage} placeholder={t('meta.group1_placeholder')} onChange={(e) => setA({ ...a, label1: e.target.value })} />
        </Field>
        <Field label={t('meta.group2')}>
          <Input value={a.label2} disabled={!canManage} placeholder={t('meta.group2_placeholder')} onChange={(e) => setA({ ...a, label2: e.target.value })} />
        </Field>
        <label className="flex items-end gap-2 pb-2 text-sm sm:col-span-2">
          <input
            type="checkbox"
            className="mb-1 accent-brand-600"
            checked={a.lower_favours_1}
            disabled={!canManage}
            onChange={(e) => setA({ ...a, lower_favours_1: e.target.checked })}
          />
          {t('meta.lower_favours_1')}
        </label>
      </div>
      <p className="text-xs text-stone-500">{t(`meta.columns_hint_${a.measure}`)}</p>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-stone-500">
              <th className="px-1 font-medium">{t('meta.study')}</th>
              {cols.map((c) => (
                <th key={c} className="px-1 font-medium">
                  {t(`meta.col_${c}`)}
                </th>
              ))}
              <th className="px-1 font-medium">{t('meta.subgroup')}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {a.rows.map((r, i) => (
              <tr key={r.id}>
                <td className="p-1">
                  <Input aria-label={`${t('meta.study')} ${i + 1}`} className="min-w-40" value={r.label} disabled={!canManage} onChange={(e) => setRow(i, { label: e.target.value })} />
                </td>
                {cols.map((c) => (
                  <td key={c} className="p-1">
                    <Input
                      aria-label={`${t(`meta.col_${c}`)} ${i + 1}`}
                      inputMode="decimal"
                      className="w-20"
                      disabled={!canManage}
                      value={cellText(r, c)}
                      onChange={(e) => {
                        setText({ ...text, [`${r.id}:${c}`]: e.target.value })
                        setRow(i, { [c]: parseNum(e.target.value) })
                      }}
                    />
                  </td>
                ))}
                <td className="p-1">
                  <Input aria-label={`${t('meta.subgroup')} ${i + 1}`} className="w-28" value={r.subgroup} disabled={!canManage} onChange={(e) => setRow(i, { subgroup: e.target.value })} />
                </td>
                <td>
                  {canManage && (
                    <button
                      type="button"
                      aria-label={t('meta.remove_row')}
                      className="px-1 text-stone-400 hover:text-red-600"
                      onClick={() => setA({ ...a, rows: a.rows.filter((_, j) => j !== i) })}
                    >
                      ×
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {canManage && (
        <>
          <div className="flex flex-wrap gap-2">
            <Button variant="ghost" className="border border-stone-300 dark:border-stone-700" onClick={() => setA({ ...a, rows: [...a.rows, { id: newId(), record_id: null, label: '', subgroup: '' }] })}>
              {t('meta.add_row')}
            </Button>
            <Button variant="ghost" className="border border-stone-300 dark:border-stone-700" disabled={!units.data?.length} onClick={addIncluded}>
              {t('meta.add_included')}
            </Button>
          </div>
          <details>
            <summary className="cursor-pointer text-sm text-brand-600">{t('meta.paste')}</summary>
            <div className="mt-2 space-y-2">
              <p className="text-xs text-stone-500">
                {t('meta.paste_hint', { cols: [t('meta.study'), ...cols.map((c) => t(`meta.col_${c}`)), t('meta.subgroup')].join(' · ') })}
              </p>
              <textarea
                rows={4}
                aria-label={t('meta.paste')}
                className="w-full rounded-md border border-stone-300 bg-white px-3 py-2 font-mono text-xs dark:border-stone-700 dark:bg-stone-900"
                value={paste}
                onChange={(e) => setPaste(e.target.value)}
              />
              <Button variant="ghost" disabled={!paste.trim()} onClick={applyPaste}>
                {t('meta.paste_apply')}
              </Button>
            </div>
          </details>
          <ErrorText error={mut.error ?? remove.error} />
          <div className="flex flex-wrap gap-2">
            <Button disabled={!a.name.trim() || a.rows.some((r) => !r.label.trim()) || mut.isPending} onClick={save}>
              {t('meta.save')}
            </Button>
            {initial && (
              <Button variant="danger" onClick={() => window.confirm(t('meta.delete_confirm')) && remove.mutate(initial.id, { onSuccess: () => onSaved('') })}>
                {t('meta.delete')}
              </Button>
            )}
          </div>
        </>
      )}
    </Card>
  )
}

function Results({ analysis }: { analysis: MetaAnalysisT }) {
  const { t } = useTranslation()
  const { project } = useProjectContext()
  const res = useMetaResult(project.id, analysis.id)
  const fmt = useFmt()
  const fmtP = useFmtP()
  const forest = useRef<SVGSVGElement>(null)
  const funnel = useRef<SVGSVGElement>(null)
  const r = res.data
  if (!r) return null
  const name = analysis.name.toLowerCase().replace(/[^a-z0-9]+/g, '-')
  const p = r.pooled
  return (
    <Card className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="mr-auto font-semibold">{t('meta.forest')}</h2>
        <Button variant="ghost" onClick={() => saveSvg(forest.current, `${name}-forest`)}>
          SVG
        </Button>
        <Button variant="ghost" onClick={() => void savePng(forest.current, `${name}-forest`)}>
          PNG
        </Button>
        <a className="px-3 text-sm text-brand-600 hover:underline" href={metaExportUrl(project.id, analysis.id)}>
          CSV
        </a>
      </div>
      {p ? (
        <div className="overflow-x-auto rounded-md border border-stone-200 dark:border-stone-800">
          <div className="min-w-[760px]">
            <ForestPlot ref={forest} analysis={analysis} result={r} />
          </div>
        </div>
      ) : (
        <p className="text-sm text-stone-500">{t('meta.no_data')}</p>
      )}
      {r.studies.some((s) => s.corrected) && <p className="text-xs text-stone-500">{t('meta.corrected_note')}</p>}
      {p && (
        <p className="text-sm">
          {t('meta.summary', {
            k: p.k,
            measure: t(`meta.measure_short_${r.measure}`),
            est: fmt(p.estimate),
            lower: fmt(p.lower),
            upper: fmt(p.upper),
            p: fmtP(p.p),
            i2: fmt(p.i2, 0),
          })}
        </p>
      )}
      {p && r.studies.filter((s) => s.yi != null).length >= 3 && (
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="mr-auto text-sm font-medium">{t('meta.funnel')}</h3>
            <Button variant="ghost" onClick={() => saveSvg(funnel.current, `${name}-funil`)}>
              SVG
            </Button>
            <Button variant="ghost" onClick={() => void savePng(funnel.current, `${name}-funil`)}>
              PNG
            </Button>
          </div>
          <div className="max-w-xl rounded-md border border-stone-200 dark:border-stone-800">
            <FunnelPlot ref={funnel} result={r} />
          </div>
          {r.egger && (
            <p className="text-sm text-stone-600 dark:text-stone-400">
              {t('meta.egger', { intercept: fmt(r.egger.intercept), p: fmtP(r.egger.p) })}{' '}
              {p.k < 10 && t('meta.egger_few')}
            </p>
          )}
        </div>
      )}
    </Card>
  )
}

export default function Meta() {
  const { t } = useTranslation()
  const { project, canManage } = useProjectContext()
  const analyses = useAnalyses(project.id)
  const [params, setParams] = useSearchParams()
  const list = analyses.data ?? []
  const adding = params.get('novo') === '1'
  const current = adding ? null : (list.find((x) => x.id === params.get('a')) ?? list[0] ?? null)

  return (
    <div className="space-y-6">
      <SynthesisNav pid={project.id} />
      <div>
        <h1 className="text-lg font-semibold">{t('meta.title')}</h1>
        <p className="text-sm text-stone-500">{t('meta.hint')}</p>
      </div>
      <div className="flex flex-wrap items-center gap-2" role="tablist">
        {list.map((x) => (
          <button
            key={x.id}
            type="button"
            role="tab"
            aria-selected={x.id === current?.id}
            onClick={() => setParams({ a: x.id })}
            className={`rounded-md px-3 py-1.5 text-sm ${x.id === current?.id ? 'bg-brand-600 text-white' : 'border border-stone-300 hover:bg-stone-100 dark:border-stone-700 dark:hover:bg-stone-800'}`}
          >
            {x.name}
          </button>
        ))}
        {canManage && (
          <button
            type="button"
            role="tab"
            aria-selected={adding}
            onClick={() => setParams({ novo: '1' })}
            className={`rounded-md px-3 py-1.5 text-sm ${adding || list.length === 0 ? 'bg-brand-600 text-white' : 'text-brand-600 hover:underline'}`}
          >
            {t('meta.new')}
          </button>
        )}
      </div>
      {analyses.isLoading ? null : current ? (
        <>
          <Editor key={current.id} initial={current} onSaved={(id) => setParams(id ? { a: id } : {})} />
          <Results key={`r-${current.id}`} analysis={current} />
        </>
      ) : canManage ? (
        <Editor key="new" initial={null} onSaved={(id) => setParams({ a: id })} />
      ) : (
        <Card>
          <p className="text-sm text-stone-500">{t('meta.none')}</p>
        </Card>
      )}
    </div>
  )
}
