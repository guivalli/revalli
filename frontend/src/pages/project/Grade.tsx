import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router-dom'
import { useAnalyses, useGrade, useGradeActions, useMetaResult, type GradePayload } from '../../api/meta'
import type { GradeDomainKey, GradeRowT, MetaAnalysisT } from '../../api/types'
import { SynthesisNav } from '../../components/SynthesisNav'
import { Button, Card, ErrorText, Field, Input, Select } from '../../components/ui'
import { download } from '../../lib/download'
import { useFmt } from '../../lib/format'
import {
  certaintyOf,
  certaintySymbols,
  csvCell,
  DOWN_DOMAINS,
  SUGGESTION_DOMAIN,
  UP_DOMAINS,
  type Certainty,
} from '../../lib/grade'
import { useProjectContext } from './context'

const CERTAINTY_STYLE: Record<Certainty, string> = {
  high: 'bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200',
  moderate: 'bg-sky-100 text-sky-900 dark:bg-sky-950 dark:text-sky-200',
  low: 'bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200',
  very_low: 'bg-red-100 text-red-900 dark:bg-red-950 dark:text-red-200',
}

const textarea =
  'w-full rounded-md border border-stone-300 bg-white px-3 py-2 text-sm dark:border-stone-700 dark:bg-stone-900'

const blank = (): GradePayload => ({
  outcome: '',
  analysis_id: null,
  design: 'rct',
  studies: null,
  participants: null,
  effect: '',
  domains: {},
  importance: 'critical',
  comments: '',
})

function CertaintyBadge({ c }: { c: Certainty }) {
  const { t } = useTranslation()
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap ${CERTAINTY_STYLE[c]}`}>
      <span aria-hidden className="tracking-tight">
        {certaintySymbols(c)}
      </span>
      {t(`grade.certainty_${c}`)}
    </span>
  )
}

/** Texto do efeito a partir do resultado da meta-análise ligada. */
function useEffectText() {
  const { t } = useTranslation()
  const fmt = useFmt()
  return (measure: string, est: number, lower: number, upper: number) =>
    t('grade.effect_auto', { measure: t(`meta.measure_short_${measure}`), est: fmt(est), lower: fmt(lower), upper: fmt(upper) })
}

function Editor({
  initial,
  analyses,
  onDone,
}: {
  initial: GradeRowT | null
  analyses: MetaAnalysisT[]
  onDone: (id: string) => void
}) {
  const { t } = useTranslation()
  const { project, canManage } = useProjectContext()
  const { create, update, remove } = useGradeActions(project.id)
  const [g, setG] = useState<GradePayload>(() => {
    if (!initial) return blank()
    const { id: _id, certainty: _c, auto: _a, suggestions: _s, ...rest } = initial
    return rest
  })
  const linked = useMetaResult(project.id, g.analysis_id ?? undefined)
  const effectText = useEffectText()
  const mut = initial ? update : create
  const certainty = certaintyOf(g)
  const setDomain = (k: GradeDomainKey, patch: Partial<{ rating: number; reason: string }>) =>
    setG({ ...g, domains: { ...g.domains, [k]: { rating: 0, reason: '', ...g.domains[k], ...patch } } })
  // Sugestões só existem depois de salvar (o servidor calcula com a análise ligada)
  const tips = initial && initial.analysis_id === g.analysis_id ? initial.suggestions : []
  const pooled = linked.data?.pooled

  const fillFromAnalysis = () => {
    if (!pooled || !linked.data) return
    const a = analyses.find((x) => x.id === g.analysis_id)
    setG({
      ...g,
      outcome: g.outcome || a?.outcome || a?.name || '',
      studies: pooled.k,
      participants: pooled.participants,
      effect: effectText(linked.data.measure, pooled.estimate, pooled.lower, pooled.upper),
    })
  }
  const save = () => {
    const done = { onSuccess: (saved: GradeRowT) => onDone(saved.id) }
    if (initial) update.mutate({ id: initial.id, body: g }, done)
    else create.mutate(g, done)
  }

  const domainRow = (k: GradeDomainKey, options: number[]) => {
    const d = g.domains[k] ?? { rating: 0, reason: '' }
    const domainTips = tips.filter((s) => SUGGESTION_DOMAIN[s] === k)
    return (
      <tr key={k} className="align-top">
        <td className="py-1.5 pr-3 text-sm font-medium">{t(`grade.domain_${k}`)}</td>
        <td className="py-1.5 pr-3">
          <Select
            aria-label={t(`grade.domain_${k}`)}
            className="w-64!"
            disabled={!canManage}
            value={d.rating}
            onChange={(e) => setDomain(k, { rating: Number(e.target.value) })}
          >
            {options.map((o) => (
              <option key={o} value={o}>
                {t(`grade.rating_${o < 0 ? 'down' : o > 0 ? 'up' : 'none'}_${Math.abs(o)}`)}
              </option>
            ))}
          </Select>
        </td>
        <td className="w-full space-y-1 py-1.5">
          <Input
            aria-label={`${t('grade.reason')}: ${t(`grade.domain_${k}`)}`}
            placeholder={t('grade.reason')}
            disabled={!canManage}
            value={d.reason}
            onChange={(e) => setDomain(k, { reason: e.target.value })}
          />
          {domainTips.map((s) => (
            <button
              key={s}
              type="button"
              disabled={!canManage}
              title={t('grade.use_suggestion')}
              onClick={() => setDomain(k, { reason: d.reason ? `${d.reason} ${t(`grade.tip_${s}`)}` : t(`grade.tip_${s}`) })}
              className="mr-1 rounded-full bg-amber-50 px-2 py-0.5 text-left text-xs text-amber-900 hover:bg-amber-100 dark:bg-amber-950 dark:text-amber-200"
            >
              💡 {t(`grade.tip_${s}`)}
            </button>
          ))}
        </td>
      </tr>
    )
  }

  return (
    <Card className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="mr-auto font-semibold">{initial ? t('grade.edit') : t('grade.new')}</h2>
        <CertaintyBadge c={certainty} />
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Field label={t('grade.outcome')}>
          <Input value={g.outcome} disabled={!canManage} onChange={(e) => setG({ ...g, outcome: e.target.value })} />
        </Field>
        <Field label={t('grade.analysis')}>
          <Select
            value={g.analysis_id ?? ''}
            disabled={!canManage}
            onChange={(e) => setG({ ...g, analysis_id: e.target.value || null })}
          >
            <option value="">{t('grade.no_analysis')}</option>
            {analyses.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={t('grade.design')} hint={t('grade.design_hint')}>
          <Select
            value={g.design}
            disabled={!canManage}
            onChange={(e) => setG({ ...g, design: e.target.value as GradePayload['design'] })}
          >
            <option value="rct">{t('grade.design_rct')}</option>
            <option value="observational">{t('grade.design_observational')}</option>
          </Select>
        </Field>
        <Field label={t('grade.studies')}>
          <Input
            type="number"
            min={0}
            value={g.studies ?? ''}
            disabled={!canManage}
            onChange={(e) => setG({ ...g, studies: e.target.value ? Number(e.target.value) : null })}
          />
        </Field>
        <Field label={t('grade.participants')}>
          <Input
            type="number"
            min={0}
            value={g.participants ?? ''}
            disabled={!canManage}
            onChange={(e) => setG({ ...g, participants: e.target.value ? Number(e.target.value) : null })}
          />
        </Field>
        <Field label={t('grade.importance')}>
          <Select
            value={g.importance}
            disabled={!canManage}
            onChange={(e) => setG({ ...g, importance: e.target.value as GradePayload['importance'] })}
          >
            {(['critical', 'important', 'limited'] as const).map((i) => (
              <option key={i} value={i}>
                {t(`grade.importance_${i}`)}
              </option>
            ))}
          </Select>
        </Field>
      </div>
      <Field label={t('grade.effect')} hint={t('grade.effect_hint')}>
        <Input value={g.effect} disabled={!canManage} onChange={(e) => setG({ ...g, effect: e.target.value })} />
      </Field>
      {g.analysis_id && pooled && canManage && (
        <div className="flex flex-wrap items-center gap-3 rounded-md bg-sky-50 px-3 py-2 text-sm text-sky-900 dark:bg-sky-950 dark:text-sky-200">
          <span className="mr-auto">
            {t('grade.from_analysis', {
              effect: effectText(linked.data!.measure, pooled.estimate, pooled.lower, pooled.upper),
              k: pooled.k,
              n: pooled.participants ?? '–',
            })}
          </span>
          <Button variant="ghost" onClick={fillFromAnalysis}>
            {t('grade.fill')}
          </Button>
        </div>
      )}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="text-left text-xs tracking-wide text-stone-500 uppercase">
              <th className="pb-1 font-medium" colSpan={3}>
                {t('grade.downgrade')}
              </th>
            </tr>
          </thead>
          <tbody>{DOWN_DOMAINS.map((k) => domainRow(k, [0, -1, -2]))}</tbody>
          <thead>
            <tr className="text-left text-xs tracking-wide text-stone-500 uppercase">
              <th className="pt-3 pb-1 font-medium" colSpan={3}>
                {t('grade.upgrade')}
              </th>
            </tr>
          </thead>
          <tbody>{UP_DOMAINS.map((k) => domainRow(k, [0, 1, 2]))}</tbody>
        </table>
      </div>
      {tips.length === 0 && g.analysis_id && initial?.analysis_id !== g.analysis_id && (
        <p className="text-xs text-stone-500">{t('grade.tips_after_save')}</p>
      )}
      <Field label={t('grade.comments')}>
        <textarea
          rows={2}
          className={textarea}
          disabled={!canManage}
          value={g.comments}
          onChange={(e) => setG({ ...g, comments: e.target.value })}
        />
      </Field>
      {canManage && (
        <>
          <ErrorText error={mut.error ?? remove.error} />
          <div className="flex flex-wrap gap-2">
            <Button disabled={!g.outcome.trim() || mut.isPending} onClick={save}>
              {t('grade.save')}
            </Button>
            {initial && (
              <Button
                variant="danger"
                onClick={() => window.confirm(t('grade.delete_confirm')) && remove.mutate(initial.id, { onSuccess: () => onDone('') })}
              >
                {t('grade.delete')}
              </Button>
            )}
          </div>
        </>
      )}
    </Card>
  )
}

export default function Grade() {
  const { t, i18n } = useTranslation()
  const { project, canManage } = useProjectContext()
  const rows = useGrade(project.id)
  const analyses = useAnalyses(project.id)
  const [params, setParams] = useSearchParams()
  const list = rows.data ?? []
  const adding = params.get('novo') === '1'
  const current = adding ? null : (list.find((x) => x.id === params.get('o')) ?? null)
  const editing = adding || !!current

  const exportCsv = () => {
    const head = [
      t('grade.outcome'),
      t('grade.studies'),
      t('grade.participants'),
      t('grade.design'),
      ...[...DOWN_DOMAINS, ...UP_DOMAINS].map((k) => t(`grade.domain_${k}`)),
      t('grade.effect'),
      t('grade.certainty'),
      t('grade.importance'),
      t('grade.comments'),
    ]
    const body = list.map((r) => [
      r.outcome,
      r.studies,
      r.participants,
      t(`grade.design_${r.design}`),
      ...[...DOWN_DOMAINS, ...UP_DOMAINS].map((k) => {
        const d = r.domains[k]
        return d && (d.rating || d.reason) ? `${d.rating > 0 ? '+' : ''}${d.rating}${d.reason ? ` (${d.reason})` : ''}` : ''
      }),
      r.effect,
      `${certaintySymbols(r.certainty)} ${t(`grade.certainty_${r.certainty}`)}`,
      t(`grade.importance_${r.importance}`),
      r.comments,
    ])
    const csv = [head, ...body].map((l) => l.map(csvCell).join(',')).join('\r\n')
    download(new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' }), 'grade-sumario-de-achados.csv')
  }

  return (
    <div className="space-y-6">
      <SynthesisNav pid={project.id} />
      <div>
        <h1 className="text-lg font-semibold">{t('grade.title')}</h1>
        <p className="text-sm text-stone-500">{t('grade.hint')}</p>
      </div>
      <Card className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="mr-auto font-semibold">{t('grade.sof')}</h2>
          {list.length > 0 && (
            <Button variant="ghost" onClick={exportCsv}>
              CSV
            </Button>
          )}
          {canManage && (
            <Button onClick={() => setParams({ novo: '1' })}>{t('grade.add')}</Button>
          )}
        </div>
        {list.length === 0 && !rows.isLoading ? (
          <p className="text-sm text-stone-500">{t('grade.none')}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-stone-200 text-left text-xs text-stone-500 dark:border-stone-800">
                  <th className="py-2 pr-3 font-medium">{t('grade.outcome')}</th>
                  <th className="py-2 pr-3 font-medium">{t('grade.studies_short')}</th>
                  <th className="py-2 pr-3 font-medium">{t('grade.effect')}</th>
                  <th className="py-2 pr-3 font-medium">{t('grade.certainty')}</th>
                  <th className="py-2 pr-3 font-medium">{t('grade.importance')}</th>
                  <th className="py-2 font-medium">{t('grade.comments')}</th>
                </tr>
              </thead>
              <tbody>
                {list.map((r) => {
                  const reasons = [...DOWN_DOMAINS, ...UP_DOMAINS]
                    .filter((k) => r.domains[k]?.rating)
                    .map((k) => {
                      const d = r.domains[k]!
                      return `${t(`grade.domain_${k}`)} (${d.rating > 0 ? '+' : ''}${d.rating})`
                    })
                  return (
                    <tr
                      key={r.id}
                      onClick={() => setParams({ o: r.id })}
                      className={`cursor-pointer border-b border-stone-100 align-top hover:bg-stone-50 dark:border-stone-800 dark:hover:bg-stone-800 ${r.id === current?.id ? 'bg-stone-50 dark:bg-stone-800' : ''}`}
                    >
                      <td className="py-2 pr-3 font-medium">
                        <button type="button" className="text-left hover:underline" onClick={() => setParams({ o: r.id })}>
                          {r.outcome}
                        </button>
                      </td>
                      <td className="py-2 pr-3 whitespace-nowrap">
                        {t('grade.studies_cell', { k: r.studies ?? '–', n: r.participants?.toLocaleString(i18n.language) ?? '–' })}
                        <div className="text-xs text-stone-500">{t(`grade.design_${r.design}`)}</div>
                      </td>
                      <td className="py-2 pr-3">{r.effect || '–'}</td>
                      <td className="py-2 pr-3">
                        <CertaintyBadge c={r.certainty} />
                        {reasons.length > 0 && <div className="mt-1 text-xs text-stone-500">{reasons.join('; ')}</div>}
                      </td>
                      <td className="py-2 pr-3">{t(`grade.importance_${r.importance}`)}</td>
                      <td className="py-2 text-stone-600 dark:text-stone-400">{r.comments}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      {editing && (
        <Editor
          key={current?.id ?? 'new'}
          initial={current}
          analyses={analyses.data ?? []}
          onDone={(id) => setParams(id ? { o: id } : {})}
        />
      )}
    </div>
  )
}
