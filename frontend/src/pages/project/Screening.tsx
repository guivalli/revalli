import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router-dom'
import { useMe } from '../../api/hooks'
import {
  useAgreement,
  useConflicts,
  useProgress,
  useReasons,
  useScreened,
  useScreeningActions,
} from '../../api/screening'
import type { DecisionInfo, DecisionKind, Phase, Reason, ScreenedItem } from '../../api/types'
import { RecordLinks } from '../../components/RecordView'
import { Button, Card, ErrorText, Select } from '../../components/ui'
import { useProjectContext } from './context'

const PHASES: Phase[] = ['title_abstract', 'full_text']
const STATES = ['mine', 'all', 'included', 'excluded', 'conflict', 'pending'] as const

const decisionTone: Record<DecisionKind, string> = {
  include: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-100',
  exclude: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-100',
  maybe: 'bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-100',
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <Card className="p-4">
      <p className="text-sm text-stone-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums">{value.toLocaleString()}</p>
    </Card>
  )
}

function DecisionChip({ d, reasons }: { d: DecisionInfo; reasons: Reason[] }) {
  const { t } = useTranslation()
  const labels = d.reason_ids.map((id) => reasons.find((r) => r.id === id)?.label).filter(Boolean)
  return (
    <span className={`inline-block rounded-md px-2 py-0.5 text-xs ${decisionTone[d.decision]}`}>
      {d.is_final
        ? t('screening.resolved_by', { name: d.user_name ?? '?' })
        : d.user_name && `${d.user_name}: `}
      {d.is_final ? ` · ${t(`decision.${d.decision}`)}` : t(`decision.${d.decision}`)}
      {labels.length > 0 && ` (${labels.join(', ')})`}
      {d.note && <span className="block italic opacity-80">“{d.note}”</span>}
    </span>
  )
}

function ProgressSection({ phase }: { phase: Phase }) {
  const { t, i18n } = useTranslation()
  const { project } = useProjectContext()
  const { data: p } = useProgress(project.id, phase)
  const { data: me } = useMe()
  const agreement = useAgreement(project.id, phase)
  if (!p) return null
  const canScreen = project.my_role === 'lead' || project.my_role === 'reviewer'
  const started = (p.reviewers.find((r) => r.user_id === me?.id)?.decided ?? 0) > 0
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <Stat label={t('screening.eligible')} value={p.eligible} />
        <Stat label={t('screening.included')} value={p.included} />
        <Stat label={t('screening.excluded')} value={p.excluded} />
        <Stat label={t('screening.conflicts')} value={p.conflicts} />
        <Stat label={t('screening.pending')} value={p.pending} />
      </div>
      <div className="flex flex-wrap items-center gap-4">
        {canScreen ? (
          p.remaining_for_me > 0 ? (
            <Link
              to={`sessao?fase=${phase}`}
              className="rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700"
            >
              {started ? t('screening.continue') : t('screening.start')} ({p.remaining_for_me})
            </Link>
          ) : (
            <span className="text-sm text-stone-500">{t('screening.done_title')}</span>
          )
        ) : (
          <span className="text-sm text-stone-500">{t('screening.not_reviewer')}</span>
        )}
        <span className="text-sm text-stone-500">
          {t('screening.required', { count: p.reviewers_required })} ·{' '}
          {p.blind ? t('screening.blind_on') : t('screening.blind_off')}
        </span>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="overflow-x-auto p-4">
          <h2 className="mb-3 font-semibold">{t('screening.reviewers')}</h2>
          <table className="w-full text-sm">
            <thead className="text-left text-stone-500">
              <tr>
                <th className="py-1 font-normal">{t('screening.reviewer')}</th>
                <th className="py-1 text-right font-normal">{t('screening.decided')}</th>
                <th className="py-1 text-right font-normal">{t('decision.include')}</th>
                <th className="py-1 text-right font-normal">{t('decision.exclude')}</th>
                <th className="py-1 text-right font-normal">{t('decision.maybe')}</th>
              </tr>
            </thead>
            <tbody className="tabular-nums">
              {p.reviewers.map((r) => (
                <tr key={r.user_id} className="border-t border-stone-100 dark:border-stone-800">
                  <td className="py-1">{r.full_name}</td>
                  <td className="py-1 text-right">{r.decided}</td>
                  <td className="py-1 text-right">{r.included}</td>
                  <td className="py-1 text-right">{r.excluded}</td>
                  <td className="py-1 text-right">{r.maybe}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
        <Card className="overflow-x-auto p-4">
          <h2 className="mb-1 font-semibold">{t('screening.agreement')}</h2>
          <p className="mb-3 text-xs text-stone-500">{t('screening.kappa_hint')}</p>
          {agreement.data?.pairs.length ? (
            <table className="w-full text-sm">
              <thead className="text-left text-stone-500">
                <tr>
                  <th className="py-1 font-normal">{t('screening.pair')}</th>
                  <th className="py-1 text-right font-normal">{t('screening.n')}</th>
                  <th className="py-1 text-right font-normal">{t('screening.percent')}</th>
                  <th className="py-1 text-right font-normal">{t('screening.kappa')}</th>
                </tr>
              </thead>
              <tbody className="tabular-nums">
                {agreement.data.pairs.map((a) => (
                  <tr key={`${a.user_a}-${a.user_b}`} className="border-t border-stone-100 dark:border-stone-800">
                    <td className="py-1">
                      {a.user_a} × {a.user_b}
                    </td>
                    <td className="py-1 text-right">{a.n}</td>
                    <td className="py-1 text-right">{a.percent == null ? '–' : `${a.percent.toLocaleString(i18n.language)}%`}</td>
                    <td className="py-1 text-right">{a.kappa == null ? '–' : a.kappa.toLocaleString(i18n.language, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="text-sm text-stone-500">{t('screening.no_pairs')}</p>
          )}
        </Card>
      </div>
    </div>
  )
}

function ConflictsSection({ phase, reasons }: { phase: Phase; reasons: Reason[] }) {
  const { t } = useTranslation()
  const { project, canManage } = useProjectContext()
  const canResolve = canManage || project.my_role === 'arbitrator'
  const [page, setPage] = useState(1)
  const progress = useProgress(project.id, phase)
  // Com cegamento, só árbitros veem as decisões dos outros
  const blind = !!progress.data?.blind && project.my_role !== 'arbitrator'
  const conflicts = useConflicts(project.id, phase, page, canResolve && !!progress.data && !blind)
  const { resolve } = useScreeningActions(project.id, phase)
  const [reasonFor, setReasonFor] = useState<Record<string, string>>({})
  if (!canResolve) return null
  const data = conflicts.data
  return (
    <Card className="space-y-4 p-4">
      <h2 className="font-semibold">
        {t('screening.conflicts_title')}
        {!!data?.total && <span className="ml-2 text-sm font-normal text-stone-500">({data.total})</span>}
      </h2>
      {blind ? (
        <p className="text-sm text-stone-500">
          {t('screening.blind_conflicts')}{' '}
          <Link to="../protocolo" className="text-brand-600 underline">
            {t('tabs.protocol')}
          </Link>
        </p>
      ) : !data?.items.length ? (
        <p className="text-sm text-stone-500">{t('screening.no_conflicts')}</p>
      ) : (
        <ul className="space-y-4">
          {data.items.map(({ record: r, decisions }) => (
            <li key={r.id} className="space-y-2 border-t border-stone-100 pt-3 dark:border-stone-800">
              <p className="font-medium">{r.title || t('records.no_title')}</p>
              <p className="text-xs text-stone-500">
                {r.authors.slice(0, 3).join('; ')}
                {r.authors.length > 3 && ' et al.'} {r.year && `· ${r.year}`} {r.journal && `· ${r.journal}`}
              </p>
              <RecordLinks r={r} />
              {r.abstract && (
                <details className="text-sm">
                  <summary className="cursor-pointer text-stone-500">{t('screening.abstract')}</summary>
                  <p className="mt-1 whitespace-pre-line">{r.abstract}</p>
                </details>
              )}
              <div className="flex flex-wrap gap-2">
                {decisions.map((d, i) => (
                  <DecisionChip key={i} d={d} reasons={reasons} />
                ))}
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  disabled={resolve.isPending}
                  onClick={() => resolve.mutate({ record_id: r.id, decision: 'include' })}
                >
                  {t('screening.final_include')}
                </Button>
                <Select
                  className="sm:w-56"
                  aria-label={t('screening.reasons')}
                  value={reasonFor[r.id] ?? ''}
                  onChange={(e) => setReasonFor({ ...reasonFor, [r.id]: e.target.value })}
                >
                  <option value="">{t('screening.reasons')}…</option>
                  {reasons
                    .filter((x) => !x.archived)
                    .map((x) => (
                      <option key={x.id} value={x.id}>
                        {x.label}
                      </option>
                    ))}
                </Select>
                <Button
                  variant="danger"
                  disabled={resolve.isPending}
                  onClick={() =>
                    resolve.mutate({
                      record_id: r.id,
                      decision: 'exclude',
                      reason_ids: reasonFor[r.id] ? [reasonFor[r.id]] : [],
                    })
                  }
                >
                  {t('screening.final_exclude')}
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}
      <ErrorText error={resolve.error} />
      {!!data && data.total > 10 && (
        <Pager page={page} pages={Math.ceil(data.total / 10)} onChange={setPage} />
      )}
    </Card>
  )
}

function Pager({ page, pages, onChange }: { page: number; pages: number; onChange: (p: number) => void }) {
  const { t } = useTranslation()
  return (
    <div className="flex items-center justify-between text-sm">
      <Button variant="ghost" disabled={page <= 1} onClick={() => onChange(page - 1)}>
        {t('records.prev')}
      </Button>
      <span className="text-stone-500">{t('records.page', { page, pages })}</span>
      <Button variant="ghost" disabled={page >= pages} onClick={() => onChange(page + 1)}>
        {t('records.next')}
      </Button>
    </div>
  )
}

function ScreenedRow({ item, phase, reasons }: { item: ScreenedItem; phase: Phase; reasons: Reason[] }) {
  const { t } = useTranslation()
  const { project } = useProjectContext()
  const { decide } = useScreeningActions(project.id, phase)
  const r = item.record
  const mine = r.my_decision
  const resolved = item.decisions.some((d) => d.is_final)
  return (
    <li className="space-y-2 border-t border-stone-100 py-3 dark:border-stone-800">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="font-medium">{r.title || t('records.no_title')}</p>
          <p className="text-xs text-stone-500">
            {r.authors.slice(0, 3).join('; ')}
            {r.authors.length > 3 && ' et al.'} {r.year && `· ${r.year}`}
          </p>
        </div>
        <span className="shrink-0 rounded-full bg-stone-100 px-2 py-0.5 text-xs dark:bg-stone-800">
          {t(`state.${item.state}`)}
        </span>
      </div>
      <div className="flex flex-wrap gap-2">
        {item.decisions.map((d, i) => (
          <DecisionChip key={i} d={d} reasons={reasons} />
        ))}
        {mine?.labels.map((l) => (
          <span key={l} className="rounded-full bg-brand-50 px-2 py-0.5 text-xs text-brand-700 dark:bg-stone-800 dark:text-brand-100">
            {l}
          </span>
        ))}
      </div>
      {mine && !resolved && (
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="text-stone-500">{t('screening.change')}:</span>
          {(['include', 'maybe', 'exclude'] as const)
            .filter((k) => k !== mine.decision)
            .map((k) => (
              <button
                key={k}
                type="button"
                disabled={decide.isPending}
                className="rounded-md border border-stone-300 px-2 py-0.5 hover:bg-stone-100 dark:border-stone-700 dark:hover:bg-stone-800"
                onClick={() =>
                  decide.mutate({ record_id: r.id, decision: k, labels: mine.labels, note: mine.note })
                }
              >
                {t(`decision.${k}`)}
              </button>
            ))}
          <ErrorText error={decide.error} />
        </div>
      )}
    </li>
  )
}

function ScreenedSection({ phase, reasons }: { phase: Phase; reasons: Reason[] }) {
  const { t } = useTranslation()
  const { project } = useProjectContext()
  const [state, setState] = useState<(typeof STATES)[number]>('mine')
  const [decision, setDecision] = useState<DecisionKind | ''>('')
  const [page, setPage] = useState(1)
  const { data } = useScreened(project.id, phase, state, page, state === 'mine' && decision ? decision : undefined)
  return (
    <Card className="space-y-3 p-4">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="mr-auto font-semibold">
          {state === 'mine' ? t('screening.my_decisions') : t('screening.all_records')}
        </h2>
        <Select
          className="sm:w-56"
          aria-label={t('screening.filter_state')}
          value={state}
          onChange={(e) => {
            setState(e.target.value as (typeof STATES)[number])
            setPage(1)
          }}
        >
          {STATES.map((s) => (
            <option key={s} value={s}>
              {s === 'mine' ? t('screening.my_decisions') : s === 'all' ? t('screening.all_records') : t(`state.${s}`)}
            </option>
          ))}
        </Select>
        {state === 'mine' && (
          <Select
            className="sm:w-40"
            aria-label={t('screening.filter_decision')}
            value={decision}
            onChange={(e) => {
              setDecision(e.target.value as DecisionKind | '')
              setPage(1)
            }}
          >
            <option value="">{t('records.filter_all')}</option>
            {(['include', 'maybe', 'exclude'] as const).map((k) => (
              <option key={k} value={k}>
                {t(`decision.${k}`)}
              </option>
            ))}
          </Select>
        )}
      </div>
      {data?.items.length ? (
        <ul>
          {data.items.map((it) => (
            <ScreenedRow key={it.record.id} item={it} phase={phase} reasons={reasons} />
          ))}
        </ul>
      ) : (
        <p className="text-sm text-stone-500">{t('screening.no_items')}</p>
      )}
      {!!data && data.total > 20 && <Pager page={page} pages={Math.ceil(data.total / 20)} onChange={setPage} />}
    </Card>
  )
}

export default function Screening() {
  const { t } = useTranslation()
  const { project } = useProjectContext()
  const [params, setParams] = useSearchParams()
  const phase: Phase = params.get('fase') === 'full_text' ? 'full_text' : 'title_abstract'
  const reasons = useReasons(project.id).data ?? []
  return (
    <div className="space-y-6">
      <div role="tablist" className="inline-flex rounded-md border border-stone-300 p-0.5 dark:border-stone-700">
        {PHASES.map((ph) => (
          <button
            key={ph}
            role="tab"
            aria-selected={ph === phase}
            type="button"
            onClick={() => setParams({ fase: ph })}
            className={`rounded px-3 py-1 text-sm ${
              ph === phase ? 'bg-brand-600 text-white' : 'text-stone-600 hover:bg-stone-100 dark:text-stone-300 dark:hover:bg-stone-800'
            }`}
          >
            {t(`screening.phase_${ph}`)}
          </button>
        ))}
      </div>
      <ProgressSection key={`p-${phase}`} phase={phase} />
      <ConflictsSection key={`c-${phase}`} phase={phase} reasons={reasons} />
      <ScreenedSection key={`s-${phase}`} phase={phase} reasons={reasons} />
    </div>
  )
}
