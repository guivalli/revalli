import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import {
  useAIFlags,
  useAIUsage,
  useCalibration,
  useCurve,
  useInstanceAI,
  useProjectAI,
  useProjectAIActions,
} from '../../api/ai'
import { useMe } from '../../api/hooks'
import type { AIScope, Phase, ProjectAISettings } from '../../api/types'
import { AISuggestionChip } from '../../components/AISuggestionChip'
import { CriteriaMissing } from '../../components/CriteriaMissing'
import { Button, Card, ErrorText, Field, Input, Select } from '../../components/ui'
import { ApiError } from '../../api/client'
import { useProjectContext } from './context'

const area =
  'w-full rounded-md border border-stone-300 bg-white px-3 py-2 text-sm dark:border-stone-700 dark:bg-stone-900 disabled:opacity-70'

function SettingsCard({ initial }: { initial: ProjectAISettings }) {
  const { t } = useTranslation()
  const { project, canManage } = useProjectContext()
  const { save } = useProjectAIActions(project.id)
  const [s, setS] = useState(initial)
  return (
    <Card className="space-y-4">
      <h2 className="font-semibold">{t('ai.project_title')}</h2>
      <fieldset disabled={!canManage} className="space-y-4">
        {[
          ['enabled', 'ai.enabled', 'ai.enabled_hint'],
          ['local_only', 'ai.local_only', 'ai.local_only_hint'],
          ['active_learning', 'ai.active_learning', 'ai.active_learning_hint'],
          ['suggest_tags', 'ai.suggest_tags', 'ai.suggest_tags_hint'],
          ['suggest_reasons', 'ai.suggest_reasons', 'ai.suggest_reasons_hint'],
        ].map(([k, label, hint]) => (
          <label key={k} className="flex items-start gap-3">
            <input
              type="checkbox"
              className="mt-1 size-4 accent-brand-600"
              checked={s[k as 'enabled' | 'local_only' | 'active_learning' | 'suggest_tags' | 'suggest_reasons']}
              onChange={(e) => setS({ ...s, [k]: e.target.checked })}
            />
            <span>
              <span className="block text-sm font-medium">{t(label)}</span>
              <span className="block text-xs text-stone-500">{t(hint)}</span>
            </span>
          </label>
        ))}
        <div className="space-y-2">
          <p className="text-sm font-medium">{t('ai.mode')}</p>
          {(['suggest', 'second_reviewer'] as const).map((m) => (
            <label key={m} className="flex items-start gap-3">
              <input
                type="radio"
                name="mode"
                className="mt-1 size-4 accent-brand-600"
                checked={s.mode === m}
                onChange={() => setS({ ...s, mode: m })}
              />
              <span>
                <span className="block text-sm">{t(`ai.mode_${m}`)}</span>
                <span className="block text-xs text-stone-500">{t(`ai.mode_${m}_hint`)}</span>
              </span>
            </label>
          ))}
        </div>
        <div className="space-y-2">
          <p className="text-sm font-medium">{t('ai.reveal')}</p>
          {(['after', 'before'] as const).map((m) => (
            <label key={m} className="flex items-start gap-3">
              <input
                type="radio"
                name="reveal"
                className="mt-1 size-4 accent-brand-600"
                checked={s.reveal_suggestions === m}
                onChange={() => setS({ ...s, reveal_suggestions: m })}
              />
              <span>
                <span className="block text-sm">{t(`ai.reveal_${m}`)}</span>
                <span className="block text-xs text-stone-500">{t(`ai.reveal_${m}_hint`)}</span>
              </span>
            </label>
          ))}
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={t('ai.budget')} hint={t('ai.budget_hint')}>
            <Input
              type="number"
              min={0}
              step="0.5"
              value={s.budget_usd ?? ''}
              onChange={(e) => setS({ ...s, budget_usd: e.target.value === '' ? null : Number(e.target.value) })}
            />
          </Field>
          <Field label={t('ai.stop_after')} hint={t('ai.stop_after_hint')}>
            <Input
              type="number"
              min={10}
              value={s.stop_after_irrelevant}
              onChange={(e) => setS({ ...s, stop_after_irrelevant: Number(e.target.value) })}
            />
          </Field>
        </div>
        <Field label={t('ai.extra')} hint={t('ai.extra_hint')}>
          <textarea
            rows={3}
            className={area}
            value={s.extra_instructions}
            onChange={(e) => setS({ ...s, extra_instructions: e.target.value })}
          />
        </Field>
      </fieldset>
      <ErrorText error={save.error} />
      {save.isSuccess && (
        <p role="status" className="text-sm text-brand-700 dark:text-brand-100">
          {t('ai.saved')}
        </p>
      )}
      {canManage && (
        <Button onClick={() => save.mutate(s)} disabled={save.isPending}>
          {t('ai.save_project')}
        </Button>
      )}
    </Card>
  )
}

const isCriteriaMissing = (e: unknown) => e instanceof ApiError && e.code === 'criteria_missing'

function RunCard({ phase }: { phase: Phase }) {
  const { t, i18n } = useTranslation()
  const { project } = useProjectContext()
  const { estimate, run } = useProjectAIActions(project.id)
  const [scope, setScope] = useState<AIScope>('pending')
  const [limit, setLimit] = useState('')
  const body = { phase, scope, limit: limit ? Number(limit) : scope === 'calibration' ? 100 : null }
  const money = (v: number) =>
    v.toLocaleString(i18n.language, { style: 'currency', currency: 'USD', maximumFractionDigits: 4 })
  const e = estimate.data
  return (
    <Card className="space-y-4">
      <h2 className="font-semibold">{t('ai.run_title')}</h2>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t('ai.scope')}>
          <Select
            value={scope}
            onChange={(ev) => {
              setScope(ev.target.value as AIScope)
              estimate.reset()
            }}
          >
            {(['pending', 'excluded', 'calibration'] as const).map((s) => (
              <option key={s} value={s}>
                {t(`ai.scope_${s}`)}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={t('ai.limit')} hint={scope === 'calibration' ? t('ai.limit_calibration') : t('ai.limit_hint')}>
          <Input
            type="number"
            min={1}
            value={limit}
            onChange={(ev) => {
              setLimit(ev.target.value)
              estimate.reset()
            }}
          />
        </Field>
      </div>
      <p className="text-xs text-stone-500">{t(`ai.scope_${scope}_hint`)}</p>
      <div className="flex flex-wrap gap-2">
        <Button variant="ghost" onClick={() => estimate.mutate(body)} disabled={estimate.isPending}>
          {t('ai.estimate')}
        </Button>
        <Button
          onClick={() => run.mutate(body)}
          disabled={run.isPending || !e || e.records === 0}
        >
          {t('ai.run')}
        </Button>
      </div>
      {e && (
        <p role="status" className="text-sm">
          {t('ai.estimate_result', { records: e.records, cached: e.cached })}{' '}
          {e.local
            ? t('ai.estimate_local')
            : t('ai.estimate_cost', { cost: money(e.cost_usd), spent: money(e.spent_usd) })}
          {e.budget_usd != null && ` ${t('ai.estimate_budget', { budget: money(e.budget_usd) })}`}
        </p>
      )}
      {run.isSuccess && <p className="text-sm text-brand-700 dark:text-brand-100">{t('ai.started')}</p>}
      <CriteriaMissing error={estimate.error ?? run.error} pid={project.id} />
      <ErrorText error={isCriteriaMissing(estimate.error ?? run.error) ? null : (estimate.error ?? run.error)} />
    </Card>
  )
}

function CurveChart({ points, total }: { points: { screened: number; found: number }[]; total: number }) {
  const { t } = useTranslation()
  const w = 520
  const h = 180
  const pad = 32
  const maxX = Math.max(total, 1)
  const maxY = Math.max(...points.map((p) => p.found), 1)
  const x = (v: number) => pad + (v / maxX) * (w - pad - 8)
  const y = (v: number) => h - pad - (v / maxY) * (h - pad - 8)
  const path = points.map((p, i) => `${i ? 'L' : 'M'}${x(p.screened)},${y(p.found)}`).join(' ')
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full max-w-xl" role="img" aria-label={t('ai.curve_title')}>
      <line x1={pad} y1={h - pad} x2={w - 8} y2={h - pad} className="stroke-stone-300 dark:stroke-stone-600" />
      <line x1={pad} y1={8} x2={pad} y2={h - pad} className="stroke-stone-300 dark:stroke-stone-600" />
      <line
        x1={x(0)}
        y1={y(0)}
        x2={x(maxX)}
        y2={y(maxY)}
        strokeDasharray="4 4"
        className="stroke-stone-300 dark:stroke-stone-600"
      />
      <path d={`M${x(0)},${y(0)} ${path.replace(/^M/, 'L')}`} fill="none" strokeWidth={2} className="stroke-brand-600" />
      <text x={pad} y={h - 10} fontSize={11} className="fill-stone-500">
        0
      </text>
      <text x={w - 8} y={h - 10} fontSize={11} textAnchor="end" className="fill-stone-500">
        {t('ai.curve_x', { count: maxX })}
      </text>
      <text x={pad - 6} y={14} fontSize={11} textAnchor="end" className="fill-stone-500">
        {maxY}
      </text>
    </svg>
  )
}

function PriorityCard() {
  const { t } = useTranslation()
  const { project, canManage } = useProjectContext()
  const { data: c } = useCurve(project.id)
  const { embed } = useProjectAIActions(project.id)
  return (
    <Card className="space-y-3">
      <h2 className="font-semibold">{t('ai.curve_title')}</h2>
      <p className="text-xs text-stone-500">{t('ai.curve_hint')}</p>
      {canManage && (
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="ghost" onClick={() => embed.mutate()} disabled={embed.isPending}>
            {t('ai.embed')}
          </Button>
          <span className="text-xs text-stone-500">{t('ai.embed_hint')}</span>
        </div>
      )}
      <ErrorText error={embed.error} />
      {c && (
        <>
          <p className="text-sm">
            {t('ai.curve_stats', { screened: c.screened, total: c.total, found: c.found, since: c.since_last_include })}{' '}
            {c.expected_remaining != null && t('ai.curve_expected', { n: c.expected_remaining })}
          </p>
          <p className="text-xs text-stone-500">{c.prioritized ? t('ai.prioritized_on') : t('ai.prioritized_off')}</p>
          {c.points.length > 1 && <CurveChart points={c.points} total={c.total} />}
          {c.should_stop && (
            <p className="rounded-md bg-emerald-50 p-3 text-sm text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200">
              {t('ai.should_stop', { n: c.stop_after_irrelevant })}
            </p>
          )}
        </>
      )}
    </Card>
  )
}

function Metric({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div title={hint}>
      <p className="text-sm text-stone-500">{label}</p>
      <p className="text-xl font-semibold tabular-nums">{value}</p>
    </div>
  )
}

function CalibrationCard({ phase }: { phase: Phase }) {
  const { t, i18n } = useTranslation()
  const { project } = useProjectContext()
  const { data: c } = useCalibration(project.id, phase)
  const pct = (v: number | null) => (v == null ? '–' : `${(v * 100).toLocaleString(i18n.language, { maximumFractionDigits: 1 })}%`)
  return (
    <Card className="space-y-3">
      <h2 className="font-semibold">{t('ai.calibration_title')}</h2>
      <p className="text-xs text-stone-500">{t('ai.calibration_hint')}</p>
      {c && c.n > 0 ? (
        <>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <Metric label={t('ai.n')} value={String(c.n)} hint="" />
            <Metric label={t('ai.sensitivity')} value={pct(c.sensitivity)} hint={t('ai.sensitivity_hint')} />
            <Metric label={t('ai.specificity')} value={pct(c.specificity)} hint={t('ai.specificity_hint')} />
            <Metric
              label={t('screening.kappa')}
              value={c.kappa == null ? '–' : c.kappa.toLocaleString(i18n.language, { minimumFractionDigits: 2 })}
              hint={t('screening.kappa_hint')}
            />
          </div>
          <p className="text-sm text-stone-600 dark:text-stone-300">
            {t('ai.confusion', { tp: c.tp, fn: c.fn, tn: c.tn, fp: c.fp, maybe: c.maybe })}
          </p>
          {c.sensitivity != null && c.sensitivity < 0.95 && (
            <p className="text-sm text-amber-700 dark:text-amber-300">{t('ai.low_recall')}</p>
          )}
        </>
      ) : (
        <p className="text-sm text-stone-500">{t('ai.no_calibration')}</p>
      )}
    </Card>
  )
}

function FlagsCard({ phase }: { phase: Phase }) {
  const { t } = useTranslation()
  const { project, canManage } = useProjectContext()
  const allowed = canManage || project.my_role === 'arbitrator'
  const { data } = useAIFlags(project.id, phase, allowed)
  if (!allowed) return null
  return (
    <Card className="space-y-3">
      <h2 className="font-semibold">{t('ai.flags_title')}</h2>
      <p className="text-xs text-stone-500">{t('ai.flags_hint')}</p>
      {data?.length ? (
        <ul className="space-y-3">
          {data.map(({ record: r, suggestion }) => (
            <li key={r.id} className="space-y-1 border-t border-stone-100 pt-2 dark:border-stone-800">
              <p className="font-medium">{r.title || t('records.no_title')}</p>
              <p className="text-xs text-stone-500">
                {r.authors.slice(0, 3).join('; ')} {r.year && `· ${r.year}`}
              </p>
              <AISuggestionChip s={suggestion} />
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-stone-500">{t('ai.no_flags')}</p>
      )}
    </Card>
  )
}

export default function AI() {
  const { t, i18n } = useTranslation()
  const { project, canManage } = useProjectContext()
  const { data: me } = useMe()
  const settings = useProjectAI(project.id)
  const instance = useInstanceAI()
  const usage = useAIUsage(project.id)
  const [phase, setPhase] = useState<Phase>('title_abstract')
  const configured = !!instance.data?.screening.provider_id && !!instance.data?.screening.model

  return (
    <div className="space-y-6">
      {!configured && (
        <p className="rounded-md bg-amber-50 p-3 text-sm text-amber-800 dark:bg-amber-950 dark:text-amber-200">
          {t('ai.not_configured')}{' '}
          {me?.is_admin && (
            <Link to="/ia" className="underline">
              {t('ai.configure')}
            </Link>
          )}
        </p>
      )}
      {settings.data && <SettingsCard initial={settings.data} />}
      {settings.data?.enabled && (
        <>
          <div role="tablist" className="inline-flex rounded-md border border-stone-300 p-0.5 dark:border-stone-700">
            {(['title_abstract', 'full_text'] as const).map((ph) => (
              <button
                key={ph}
                role="tab"
                type="button"
                aria-selected={ph === phase}
                onClick={() => setPhase(ph)}
                className={`rounded px-3 py-1 text-sm ${ph === phase ? 'bg-brand-600 text-white' : 'text-stone-600 hover:bg-stone-100 dark:text-stone-300 dark:hover:bg-stone-800'}`}
              >
                {t(`screening.phase_${ph}`)}
              </button>
            ))}
          </div>
          {canManage && configured && <RunCard key={phase} phase={phase} />}
          <CalibrationCard phase={phase} />
          {phase === 'title_abstract' && <PriorityCard />}
          <FlagsCard phase={phase} />
        </>
      )}
      {usage.data && usage.data.calls > 0 && (
        <p className="text-sm text-stone-500">
          {t('ai.usage', {
            calls: usage.data.calls,
            tokens: (usage.data.input_tokens + usage.data.output_tokens).toLocaleString(i18n.language),
            cost: usage.data.spent_usd.toLocaleString(i18n.language, { style: 'currency', currency: 'USD' }),
          })}
        </p>
      )}
    </div>
  )
}
