import type { TFunction } from 'i18next'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { useMembers } from '../../api/hooks'
import { useActiveJobs, useRecentJobs, useRecordActions, useSummary } from '../../api/records'
import { useProgress } from '../../api/screening'
import type { Phase, Progress } from '../../api/types'
import { useWatches } from '../../api/watches'
import { ProgressRing } from '../../components/ProgressRing'
import { Button, Card, ErrorText, Section } from '../../components/ui'
import { useProjectContext } from './context'
import { QuickSetup } from './QuickSetup'

// Cores de estado fixas (inclui, exclui, atenção); o texto e o ícone dizem o mesmo que a cor
const STATUS = { good: '#0ca30c', critical: '#d03b3b', warning: '#fab219', neutral: '#a8a29e' }

const linkButton =
  'inline-flex items-center justify-center rounded-md px-3 py-2 text-sm font-medium transition'
const primaryLink = `${linkButton} bg-brand-600 text-white hover:bg-brand-700`
const quietLink = `${linkButton} border border-stone-300 text-stone-700 hover:bg-stone-100 dark:border-stone-700 dark:text-stone-300 dark:hover:bg-stone-800`

/** Troca erros técnicos de IA por uma instrução; o resto aparece como veio do worker. */
function jobError(t: TFunction, error: string): string {
  if (/^AIError: connection\b/.test(error)) return t('jobs.error_ai_unreachable')
  if (/^AIError: embeddings_unsupported\b/.test(error)) return t('jobs.error_embeddings_unsupported')
  return error
}

function Tile({
  label,
  value,
  warn,
  children,
}: {
  label: string
  value: number
  warn?: boolean
  children?: React.ReactNode
}) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border border-stone-200 p-4 text-center dark:border-stone-800">
      <p className="flex min-h-10 items-center text-sm text-stone-500">{label}</p>
      <p
        className={`text-4xl font-semibold tabular-nums ${warn && value > 0 ? 'text-amber-700 dark:text-amber-300' : ''}`}
      >
        {value.toLocaleString()}
      </p>
      <div className="mt-auto w-full">{children}</div>
    </div>
  )
}

function InfoRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-1 sm:grid-cols-[10rem_1fr] sm:gap-4">
      <dt className="text-sm text-stone-500">{label}</dt>
      <dd className="whitespace-pre-line text-sm">{children}</dd>
    </div>
  )
}

function LegendRow({ icon, color, label, value }: { icon: string; color: string; label: string; value: number }) {
  return (
    <li className="flex items-center gap-2 text-sm">
      <span aria-hidden className="w-4 text-center font-semibold" style={{ color }}>
        {icon}
      </span>
      <span className="text-stone-600 dark:text-stone-400">{label}</span>
      <span className="ml-auto tabular-nums font-medium">{value.toLocaleString()}</span>
    </li>
  )
}

function ScreeningPhase({ phase, progress }: { phase: Phase; progress: Progress }) {
  const { t } = useTranslation()
  const decided = progress.included + progress.excluded
  const pct = progress.eligible > 0 ? Math.round((decided / progress.eligible) * 100) : 0
  const segments = [
    { value: progress.included, color: STATUS.good, label: t('screening.included') },
    { value: progress.excluded, color: STATUS.critical, label: t('screening.excluded') },
    { value: progress.conflicts, color: STATUS.warning, label: t('screening.conflicts') },
    { value: progress.pending, color: STATUS.neutral, label: t('screening.pending') },
  ]
  const started = decided + progress.conflicts > 0
  return (
    <div className="space-y-4">
      <h3 className="text-sm font-medium text-stone-500">
        {t(phase === 'title_abstract' ? 'screening.phase_title_abstract' : 'screening.phase_full_text')}
      </h3>
      <div className="flex flex-wrap items-center gap-6">
        <ProgressRing
          segments={segments}
          total={progress.eligible}
          center={`${pct}%`}
          caption={t('summary.screening_caption', { pct, total: progress.eligible })}
        />
        <div className="min-w-48 flex-1 space-y-3">
          <ul className="space-y-1.5">
            <LegendRow icon="✓" color={STATUS.good} label={segments[0].label} value={progress.included} />
            <LegendRow icon="✕" color={STATUS.critical} label={segments[1].label} value={progress.excluded} />
            <LegendRow icon="!" color={STATUS.warning} label={segments[2].label} value={progress.conflicts} />
            <LegendRow icon="…" color={STATUS.neutral} label={segments[3].label} value={progress.pending} />
          </ul>
          <p className="text-xs text-stone-500">
            {progress.remaining_for_me > 0
              ? t('summary.left_for_you', { count: progress.remaining_for_me })
              : t('summary.nothing_left_for_you')}
          </p>
        </div>
      </div>
      {phase === 'title_abstract' && (
        <Link to="triagem" className={primaryLink}>
          {started && progress.remaining_for_me > 0 ? t('summary.continue_screening') : t('summary.open_screening')}
        </Link>
      )}
    </div>
  )
}

function TeamProgress({ progress }: { progress: Progress }) {
  const { t } = useTranslation()
  if (progress.reviewers.length === 0) return null
  return (
    <div className="space-y-3">
      <h3 className="text-sm font-medium text-stone-500">{t('summary.team')}</h3>
      <ul className="space-y-3">
        {progress.reviewers.map((r) => {
          const pct = progress.eligible > 0 ? Math.min(100, (r.decided / progress.eligible) * 100) : 0
          return (
            <li key={r.user_id} className="space-y-1">
              <div className="flex items-baseline justify-between gap-2 text-sm">
                <span>{r.full_name}</span>
                <span className="tabular-nums text-stone-500">
                  {r.decided} / {progress.eligible}
                </span>
              </div>
              <div
                role="progressbar"
                aria-valuemin={0}
                aria-valuemax={progress.eligible}
                aria-valuenow={r.decided}
                aria-label={r.full_name}
                className="h-2 overflow-hidden rounded-full bg-stone-200 dark:bg-stone-800"
              >
                <div className="h-full rounded-full bg-brand-500" style={{ width: `${pct}%` }} />
              </div>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

export default function Overview() {
  const { t } = useTranslation()
  const { project, canManage } = useProjectContext()
  const { data: s } = useSummary(project.id)
  const jobs = useActiveJobs(project.id)
  const { enrich, dedup } = useRecordActions(project.id)
  const recent = useRecentJobs(project.id)
  const watches = useWatches(project.id)
  const members = useMembers(project.id)
  const titleProgress = useProgress(project.id, 'title_abstract')
  const fullProgress = useProgress(project.id, 'full_text')
  const news = (watches.data ?? []).filter((w) => w.last_status === 'ok' && w.last_new > 0)
  const busy = (jobs.data?.length ?? 0) > 0
  // Mostra a falha só se a última execução daquele tipo falhou
  const failed = [...new Map([...(recent.data ?? [])].reverse().map((j) => [j.kind, j])).values()].filter(
    (j) => j.status === 'failed',
  )

  if (!s) return null
  if (s.records_total === 0)
    return (
      <Card className="space-y-3 text-center">
        <p className="text-stone-500">{t('summary.empty')}</p>
        {canManage && (
          <Link to="importar" className="inline-block text-brand-600 dark:text-brand-300 underline">
            {t('summary.go_import')}
          </Link>
        )}
        {project.description && <p className="whitespace-pre-line">{project.description}</p>}
      </Card>
    )

  const title = titleProgress.data
  const full = fullProgress.data

  return (
    <div className="space-y-6">
      {news.map((w) => (
        <Link
          key={w.id}
          to="triagem"
          className="block rounded-md bg-brand-50 px-4 py-3 text-sm text-brand-700 hover:underline dark:bg-brand-900/30 dark:text-brand-100"
        >
          {t('watches.news', { count: w.last_new, name: w.name || w.query || w.url })}
        </Link>
      ))}

      <QuickSetup
        pid={project.id}
        canManage={canManage}
        records={s.records_total}
        pendingGroups={s.pending_groups}
        members={members.data?.length ?? 0}
        screeningStarted={
          !!title && title.included + title.excluded + title.conflicts > 0
        }
      />

      <Section
        title={t('summary.info_title')}
        actions={
          canManage && (
            <Link to="configuracoes" className={quietLink}>
              {t('tabs.settings')}
            </Link>
          )
        }
      >
        <dl className="space-y-3">
          <InfoRow label={t('summary.info_name')}>{project.title}</InfoRow>
          <InfoRow label={t('summary.info_type')}>{t(`review_type.${project.review_type}`)}</InfoRow>
          {project.my_role && <InfoRow label={t('summary.info_role')}>{t(`role.${project.my_role}`)}</InfoRow>}
          {project.description && <InfoRow label={t('summary.info_description')}>{project.description}</InfoRow>}
        </dl>
      </Section>

      <Section title={t('summary.data_title')}>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <Tile label={t('summary.identified')} value={s.records_total}>
            {canManage && (
              <Link to="importar" className={`${primaryLink} w-full`}>
                {t('summary.go_import')}
              </Link>
            )}
          </Tile>
          <Tile label={t('summary.duplicates_removed')} value={s.duplicates_removed}>
            {canManage && (
              <Button
                variant="ghost"
                className="w-full border border-stone-300 dark:border-stone-700"
                onClick={() => dedup.mutate()}
                disabled={busy || dedup.isPending}
              >
                {t('summary.dedup')}
              </Button>
            )}
          </Tile>
          <Tile label={t('summary.pending')} value={s.pending_groups} warn>
            {s.pending_groups > 0 ? (
              <Link to="duplicatas" className={`${primaryLink} w-full`}>
                {t('summary.review_now')}
              </Link>
            ) : (
              <p className="text-xs text-stone-500">{t('summary.nothing_to_review')}</p>
            )}
          </Tile>
          <Tile label={t('summary.unique')} value={s.records_unique}>
            <p className="text-xs text-stone-500">
              {t('summary.missing_abstract')}:{' '}
              <span
                className={`font-medium tabular-nums ${s.missing_abstract > 0 ? 'text-amber-700 dark:text-amber-300' : ''}`}
              >
                {s.missing_abstract.toLocaleString()}
              </span>
            </p>
            {canManage && s.missing_abstract > 0 && (
              <Button
                variant="ghost"
                className="mt-2 w-full border border-stone-300 dark:border-stone-700"
                onClick={() => enrich.mutate()}
                disabled={busy || enrich.isPending}
              >
                {t('summary.enrich')}
              </Button>
            )}
          </Tile>
        </div>
        <p className="mt-3 text-xs text-stone-500">{t('summary.enrich_hint')}</p>
        <ErrorText error={enrich.error ?? dedup.error} />
        {failed.map((j) => (
          <p key={j.id} role="alert" className="mt-2 text-sm text-red-700 dark:text-red-400">
            {t('jobs.failed', { label: t(`jobs.${j.kind}`), error: jobError(t, j.error) })}{' '}
            {j.kind === 'corpus_index' && (
              <Link to="conversa" className="underline">
                {t('jobs.open_corpus', { tab: t('tabs.corpus') })}
              </Link>
            )}
          </p>
        ))}
      </Section>

      {title && (
        <Section
          title={
            <>
              {t('tabs.screening')}{' '}
              <span className="text-sm font-normal text-stone-500">
                ({title.blind ? t('summary.blind_on') : t('summary.blind_off')})
              </span>
            </>
          }
          actions={
            canManage && (
              <Link to="protocolo" className={quietLink}>
                {t('tabs.protocol')}
              </Link>
            )
          }
        >
          <div className="grid gap-8 lg:grid-cols-2">
            <div className="space-y-8">
              <ScreeningPhase phase="title_abstract" progress={title} />
              {full && full.eligible > 0 && <ScreeningPhase phase="full_text" progress={full} />}
            </div>
            <TeamProgress progress={title} />
          </div>
        </Section>
      )}

      <Section
        title={t('members.title')}
        actions={
          <Link to="membros" className={quietLink}>
            {t('summary.manage_members')}
          </Link>
        }
      >
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-stone-500">
              <th className="py-1 font-normal">{t('summary.member_name')}</th>
              <th className="hidden py-1 font-normal sm:table-cell">{t('summary.member_email')}</th>
              <th className="py-1 text-right font-normal">{t('summary.member_role')}</th>
            </tr>
          </thead>
          <tbody>
            {(members.data ?? []).map((m) => (
              <tr key={m.user_id} className="border-t border-stone-100 dark:border-stone-800">
                <td className="py-2">{m.full_name}</td>
                <td className="hidden py-2 text-stone-500 sm:table-cell">{m.email}</td>
                <td className="py-2 text-right">{t(`role.${m.role}`)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>

      <Section title={t('summary.by_source')}>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-stone-500">
              <th className="py-1 font-normal">{t('summary.source')}</th>
              <th className="py-1 text-right font-normal">{t('summary.records')}</th>
            </tr>
          </thead>
          <tbody>
            {s.by_source.map((row) => (
              <tr key={row.source} className="border-t border-stone-100 dark:border-stone-800">
                <td className="py-2">{row.source}</td>
                <td className="py-2 text-right tabular-nums">{row.records.toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>
    </div>
  )
}
