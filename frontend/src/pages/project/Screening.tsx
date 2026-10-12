import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router-dom'
import { useAIBot, useInstanceAI, useProjectAI, useProjectAIActions, useSuggestions } from '../../api/ai'
import { ApiError } from '../../api/client'
import { pendingCsvUrl, useFileActions, useFilesSummary, usePendingFiles } from '../../api/files'
import { useMe } from '../../api/hooks'
import { useActiveJobs, useCancelJob, useRecentJobs } from '../../api/records'
import {
  useAgreement,
  useConflicts,
  useProgress,
  useReasons,
  useScreened,
  useScreeningActions,
} from '../../api/screening'
import type { AISuggestion, DecisionInfo, DecisionKind, Job, Phase, Reason, ScreenedItem } from '../../api/types'
import { AISuggestionChip } from '../../components/AISuggestionChip'
import { CriteriaMissing } from '../../components/CriteriaMissing'
import { RecordLinks } from '../../components/RecordView'
import { Button, Card, ErrorText, Select } from '../../components/ui'
import { useProjectContext } from './context'
import { StudiesSection } from './StudiesSection'

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
  // A IA só tria título e resumo: no texto completo não há sugestão para mostrar
  const aiOn = !!useProjectAI(project.id).data?.enabled && phase === 'title_abstract'
  const sugs = useSuggestions(project.id, phase, conflicts.data?.items.map((i) => i.record.id) ?? [], aiOn)
  const bot = useAIBot(project.id, aiOn).data?.user_id
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
          <Link to="../protocolo" className="text-brand-600 dark:text-brand-300 underline">
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
              <div className="flex flex-wrap items-start gap-2">
                {/* O voto da IA aparece pelo cartão da sugestão, que mostra os critérios */}
                {decisions
                  .filter((d) => !(sugs.data?.has(r.id) && d.user_id === bot))
                  .map((d, i) => (
                    <DecisionChip key={i} d={d} reasons={reasons} />
                  ))}
                {sugs.data?.get(r.id) && <AISuggestionChip s={sugs.data.get(r.id)!} />}
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

function ScreenedRow({
  item,
  phase,
  reasons,
  suggestion,
  botId,
}: {
  item: ScreenedItem
  phase: Phase
  reasons: Reason[]
  suggestion?: AISuggestion
  botId?: string
}) {
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
      <div className="flex flex-wrap items-start gap-2">
        {item.decisions
          .filter((d) => !(suggestion && d.user_id === botId))
          .map((d, i) => (
            <DecisionChip key={i} d={d} reasons={reasons} />
          ))}
        {suggestion && <AISuggestionChip s={suggestion} />}
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
  const aiOn = !!useProjectAI(project.id).data?.enabled && phase === 'title_abstract'
  const sugs = useSuggestions(project.id, phase, data?.items.map((i) => i.record.id) ?? [], aiOn)
  const bot = useAIBot(project.id, aiOn).data?.user_id
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
            <ScreenedRow
              key={it.record.id}
              item={it}
              phase={phase}
              reasons={reasons}
              suggestion={sugs.data?.get(it.record.id)}
              botId={bot}
            />
          ))}
        </ul>
      ) : (
        <p className="text-sm text-stone-500">{t('screening.no_items')}</p>
      )}
      {!!data && data.total > 20 && <Pager page={page} pages={Math.ceil(data.total / 20)} onChange={setPage} />}
    </Card>
  )
}

function lastResult(jobs: Job[] | undefined, kind: Job['kind']) {
  const job = jobs?.find((j) => j.kind === kind && j.status === 'done')
  return job?.result as Record<string, number | string[]> | undefined
}

const PENDING_SHOWN = 200

function PendingList({ pid }: { pid: string }) {
  const { t } = useTranslation()
  const pending = usePendingFiles(pid)
  const rows = pending.data ?? []
  if (rows.length === 0) return null
  const copy = () =>
    void navigator.clipboard?.writeText(
      rows.map((r) => [r.doi ?? '', r.link].filter(Boolean).join('\t')).join('\n'),
    )
  return (
    <details className="rounded-md border border-stone-200 p-3 dark:border-stone-800">
      <summary className="cursor-pointer text-sm font-medium">
        {t('pdf.pending_title', { count: rows.length })}
      </summary>
      <div className="mt-3 space-y-3">
        <p className="text-xs text-stone-500">{t('pdf.pending_help')}</p>
        <div className="flex flex-wrap gap-2">
          <a
            href={pendingCsvUrl(pid)}
            download
            className="inline-flex items-center rounded-md border border-stone-300 px-3 py-1.5 text-sm hover:bg-stone-200 dark:border-stone-700 dark:hover:bg-stone-800"
          >
            {t('pdf.pending_csv')}
          </a>
          <Button variant="ghost" onClick={copy}>
            {t('pdf.pending_copy')}
          </Button>
        </div>
        <ul className="space-y-2 text-sm">
          {rows.slice(0, PENDING_SHOWN).map((r) => (
            <li key={r.record_id} className="space-y-0.5">
              <p className="font-medium">
                {r.title}
                {r.year ? ` (${r.year})` : ''}
              </p>
              <p className="flex flex-wrap gap-x-3 text-xs text-stone-600 dark:text-stone-400">
                {r.doi && <span>DOI: {r.doi}</span>}
                {r.link && (
                  <a href={r.link} target="_blank" rel="noreferrer noopener" className="text-brand-600 dark:text-brand-300 hover:underline">
                    {t('pdf.pending_open')}
                  </a>
                )}
                {!r.link && <span>{t('pdf.pending_nolink')}</span>}
              </p>
            </li>
          ))}
        </ul>
        {rows.length > PENDING_SHOWN && (
          <p className="text-xs text-stone-500">{t('pdf.pending_more', { count: rows.length - PENDING_SHOWN })}</p>
        )}
      </div>
    </details>
  )
}

function FullTextSection() {
  const { t } = useTranslation()
  const { project, canManage } = useProjectContext()
  const summary = useFilesSummary(project.id)
  const recent = useRecentJobs(project.id)
  const { zip, openAccess } = useFileActions(project.id)
  const s = summary.data
  const zipRes = lastResult(recent.data, 'pdf_zip')
  const oaRes = lastResult(recent.data, 'pdf_oa')
  const unmatched = (zipRes?.unmatched as string[] | undefined) ?? []
  const count = (v: unknown) => (Array.isArray(v) ? v.length : Number(v ?? 0))
  const bySource = Object.entries((oaRes?.by_source ?? {}) as Record<string, number>)
  // A lista de pendentes muda quando uma busca ou um ZIP termina
  const lastRun = (recent.data ?? []).filter((j) => j.status === 'done' && j.kind.startsWith('pdf_')).length
  const queryClient = useQueryClient()
  useEffect(() => {
    void queryClient.invalidateQueries({ queryKey: ['projects', project.id, 'files'] })
  }, [lastRun, queryClient, project.id])

  return (
    <Card className="space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-lg font-semibold">{t('pdf.title')}</h2>
        {s && (
          <p className="text-sm text-stone-500">
            {[
              t('pdf.summary', { with_pdf: s.with_pdf, records: s.records }),
              s.without_text > 0 && t('pdf.without_text', { count: s.without_text }),
              s.from_open_access > 0 && t('pdf.from_oa', { count: s.from_open_access }),
            ]
              .filter(Boolean)
              .join(' · ')}
          </p>
        )}
      </div>
      {s && s.records === 0 && (
        <p role="status" className="rounded-md bg-amber-50 p-3 text-sm text-amber-900 dark:bg-amber-900/20 dark:text-amber-200">
          {t('pdf.empty_phase')}{' '}
          <Link to={`/projetos/${project.id}/protocolo`} className="font-medium underline">
            {t('pdf.empty_phase_link')}
          </Link>
        </p>
      )}
      {/* ZIP e busca de acesso aberto mexem em muitos registros de uma vez: só líderes */}
      {canManage && (
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <label className="inline-flex cursor-pointer items-center rounded-md border border-stone-300 px-3 py-2 text-sm font-medium text-stone-700 hover:bg-stone-200 dark:border-stone-700 dark:text-stone-300 dark:hover:bg-stone-800">
              <input
                type="file"
                accept=".zip,application/zip"
                className="sr-only"
                disabled={zip.isPending}
                onChange={(e) => {
                  const file = e.target.files?.[0]
                  if (file) zip.mutate(file)
                  e.target.value = ''
                }}
              />
              {zip.isPending ? t('pdf.uploading') : t('pdf.zip_button')}
            </label>
            <p className="text-xs text-stone-500">{t('pdf.zip_help')}</p>
            <ErrorText error={zip.error} />
            {zipRes && (
              <p className="text-sm">
                {t('pdf.zip_result', {
                  matched: count(zipRes.matched),
                  already: count(zipRes.already),
                  unmatched: count(zipRes.unmatched),
                  invalid: count(zipRes.invalid),
                })}
              </p>
            )}
            {unmatched.length > 0 && (
              <details className="text-xs text-stone-500">
                <summary className="cursor-pointer">{t('pdf.unmatched')}</summary>
                <ul className="mt-1 list-inside list-disc">
                  {unmatched.map((n) => (
                    <li key={n}>{n}</li>
                  ))}
                </ul>
              </details>
            )}
          </div>
          <div className="space-y-2">
            <Button
              variant="ghost"
              className="border border-stone-300 dark:border-stone-700"
              disabled={openAccess.isPending}
              onClick={() => openAccess.mutate()}
            >
              {t('pdf.oa_button')}
            </Button>
            <p className="text-xs text-stone-500">{t('pdf.oa_help')}</p>
            <ErrorText error={openAccess.error} />
            {oaRes && 'checked' in oaRes && (
              <div className="space-y-1 text-sm">
                <p>
                  {t('pdf.oa_result', {
                    checked: count(oaRes.checked),
                    found: count(oaRes.found),
                    downloaded: count(oaRes.downloaded),
                  })}
                </p>
                {bySource.length > 0 && (
                  <p className="text-xs text-stone-500">
                    {t('pdf.oa_by_source')}{' '}
                    {bySource.map(([k, n]) => `${t(`pdf.source_${k}`, { defaultValue: k })}: ${n}`).join(' · ')}
                  </p>
                )}
                {Array.isArray(oaRes.skipped) && oaRes.skipped.includes('unpaywall') && (
                  <p className="text-xs text-amber-700 dark:text-amber-300">{t('pdf.oa_unpaywall_skipped')}</p>
                )}
              </div>
            )}
          </div>
        </div>
      )}
      <PendingList pid={project.id} />
    </Card>
  )
}

const isCriteriaMissing = (e: unknown) => e instanceof ApiError && e.code === 'criteria_missing'

function AIScreenCard({ phase }: { phase: Phase }) {
  const { t, i18n } = useTranslation()
  const { project, canManage } = useProjectContext()
  const instance = useInstanceAI()
  const ai = useProjectAI(project.id)
  const { save, estimate, run } = useProjectAIActions(project.id)
  const jobs = useActiveJobs(project.id)
  const recent = useRecentJobs(project.id)
  const cancel = useCancelJob(project.id)
  const [started, setStarted] = useState(false)
  const [force, setForce] = useState(false)
  if (!canManage || !instance.data || !ai.data) return null
  const configured = !!instance.data.screening.provider_id && !!instance.data.screening.model
  const money = (v: number) =>
    v.toLocaleString(i18n.language, { style: 'currency', currency: 'USD', maximumFractionDigits: 4 })
  const body = { phase, scope: 'pending' as const, limit: null, force }
  const activeJob = (jobs.data ?? []).find((j) => j.kind === 'ai_screen')
  const running = !!activeJob
  // A última triagem desta fase, para oferecer Continuar e Refazer quando foi interrompida
  const last = (recent.data ?? []).find(
    (j) => j.kind === 'ai_screen' && (j.result as { phase?: string }).phase === phase,
  )
  const stopReason =
    last?.status === 'cancelled' ? 'user' : (last?.result as { stopped?: string } | undefined)?.stopped
  const stopped = !running && last && (stopReason === 'user' || stopReason === 'quota' || stopReason === 'budget')
    ? last
    : undefined
  const begin = (redo: boolean) => {
    setStarted(false)
    setForce(redo)
    estimate.mutate(
      { ...body, force: redo },
      {
        onSuccess: (est) => {
          // Local ou sem custo roda direto; com custo, pede confirmação
          if (est.records > 0 && (est.local || est.cost_usd === 0)) start(redo)
        },
      },
    )
  }
  const start = (redo = force) =>
    run.mutate({ ...body, force: redo }, {
      onSuccess: () => {
        setStarted(true)
        estimate.reset()
      },
    })
  const e = estimate.data
  return (
    <Card className="space-y-3">
      <div>
        <h2 className="font-semibold">{t('ai_screen.title')}</h2>
        <p className="text-sm text-stone-500">{t('ai_screen.intro')}</p>
      </div>
      {!configured ? (
        <p className="text-sm text-amber-700 dark:text-amber-300">
          {t('protocol_ai.not_configured')}{' '}
          <Link to="/ia" className="underline">
            {t('protocol_ai.go_ai')}
          </Link>
        </p>
      ) : !ai.data.enabled ? (
        <Button onClick={() => save.mutate({ ...ai.data, enabled: true })} disabled={save.isPending}>
          {t('ai_screen.enable')}
        </Button>
      ) : (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-3">
            <Button onClick={() => begin(false)} disabled={estimate.isPending || run.isPending || running}>
              {running ? t('ai_screen.running') : t('ai_screen.button')}
            </Button>
            {activeJob && (
              <Button
                variant="danger"
                className="border border-red-300 dark:border-red-800"
                disabled={cancel.isPending || activeJob.status === 'cancelling'}
                onClick={() => cancel.mutate(activeJob.id)}
              >
                {activeJob.status === 'cancelling' ? t('ai_screen.stopping') : t('ai_screen.stop')}
              </Button>
            )}
            {started && !running && (
              <Link to="sessao" className="text-sm text-brand-600 dark:text-brand-300 underline">
                {t('ai_screen.open_session')}
              </Link>
            )}
          </div>
          {stopped && !estimate.isPending && !run.isPending && (
            <div className="space-y-2 rounded-md border border-stone-300 p-3 text-sm dark:border-stone-700">
              <p>
                {t(
                  stopReason === 'quota'
                    ? 'ai_screen.stopped_quota'
                    : stopReason === 'budget'
                      ? 'ai_screen.stopped_budget'
                      : 'ai_screen.stopped',
                  {
                    done: (stopped.result as { done?: number }).done ?? 0,
                    total: (stopped.result as { total?: number }).total ?? 0,
                  },
                )}
              </p>
              <div className="flex flex-wrap gap-2">
                <Button variant="ghost" className="border border-stone-300 dark:border-stone-700" onClick={() => begin(false)}>
                  {t('ai_screen.continue')}
                </Button>
                <Button variant="ghost" className="border border-stone-300 dark:border-stone-700" onClick={() => begin(true)}>
                  {t('ai_screen.redo')}
                </Button>
              </div>
              <p className="text-xs text-stone-500">{t('ai_screen.redo_hint')}</p>
            </div>
          )}
          {e && e.records === 0 && <p className="text-sm text-stone-500">{t('ai_screen.nothing')}</p>}
          {e && e.records > 0 && !e.local && e.cost_usd > 0 && !started && (
            <div className="space-y-2 rounded-md border border-amber-300 p-3 text-sm dark:border-amber-700">
              <p>
                {t('ai.estimate_result', { records: e.records, cached: e.cached })}{' '}
                {t('ai.estimate_cost', { cost: money(e.cost_usd), spent: money(e.spent_usd) })}
              </p>
              <div className="flex gap-2">
                <Button onClick={() => start()} disabled={run.isPending}>
                  {t('ai_screen.confirm')}
                </Button>
                <Button variant="ghost" onClick={() => estimate.reset()}>
                  {t('projects.cancel')}
                </Button>
              </div>
            </div>
          )}
          <CriteriaMissing error={estimate.error ?? run.error} pid={project.id} />
          <ErrorText
            error={isCriteriaMissing(estimate.error ?? run.error) ? null : (estimate.error ?? run.error ?? cancel.error ?? save.error)}
          />
        </div>
      )}
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
      {phase === 'title_abstract' ? (
        <AIScreenCard key={`a-${phase}`} phase={phase} />
      ) : (
        <p className="text-xs text-stone-500">{t('screening.ai_title_abstract_only')}</p>
      )}
      <ProgressSection key={`p-${phase}`} phase={phase} />
      {phase === 'full_text' && <FullTextSection />}
      {phase === 'full_text' && <StudiesSection />}
      <ConflictsSection key={`c-${phase}`} phase={phase} reasons={reasons} />
      <ScreenedSection key={`s-${phase}`} phase={phase} reasons={reasons} />
    </div>
  )
}
