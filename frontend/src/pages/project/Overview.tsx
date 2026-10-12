import type { TFunction } from 'i18next'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { useActiveJobs, useRecentJobs, useRecordActions, useSummary } from '../../api/records'
import { useWatches } from '../../api/watches'
import { Button, Card, ErrorText } from '../../components/ui'
import { useProjectContext } from './context'

function Stat({ label, value, tone }: { label: string; value: number; tone?: 'warn' }) {
  return (
    <Card className="p-4">
      <p className="text-sm text-stone-500">{label}</p>
      <p
        className={`mt-1 text-2xl font-semibold tabular-nums ${tone === 'warn' && value > 0 ? 'text-amber-700 dark:text-amber-300' : ''}`}
      >
        {value.toLocaleString()}
      </p>
    </Card>
  )
}

/** Troca erros técnicos de IA por uma instrução; o resto aparece como veio do worker. */
function jobError(t: TFunction, error: string): string {
  if (/^AIError: connection\b/.test(error)) return t('jobs.error_ai_unreachable')
  if (/^AIError: embeddings_unsupported\b/.test(error)) return t('jobs.error_embeddings_unsupported')
  return error
}

export default function Overview() {
  const { t } = useTranslation()
  const { project, canManage } = useProjectContext()
  const { data: s } = useSummary(project.id)
  const jobs = useActiveJobs(project.id)
  const { enrich, dedup } = useRecordActions(project.id)
  const recent = useRecentJobs(project.id)
  const watches = useWatches(project.id)
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
          <Link to="importar" className="inline-block text-brand-600 underline">
            {t('summary.go_import')}
          </Link>
        )}
        {project.description && <p className="whitespace-pre-line">{project.description}</p>}
      </Card>
    )

  return (
    <div className="space-y-6">
      {project.description && <p className="whitespace-pre-line">{project.description}</p>}
      {news.map((w) => (
        <Link
          key={w.id}
          to="triagem"
          className="block rounded-md bg-brand-50 px-4 py-3 text-sm text-brand-700 hover:underline dark:bg-brand-900/30 dark:text-brand-100"
        >
          {t('watches.news', { count: w.last_new, name: w.name || w.query || w.url })}
        </Link>
      ))}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <Stat label={t('summary.identified')} value={s.records_total} />
        <Stat label={t('summary.duplicates_removed')} value={s.duplicates_removed} />
        <Stat label={t('summary.unique')} value={s.records_unique} />
        <Stat label={t('summary.pending')} value={s.pending_groups} tone="warn" />
        <Stat label={t('summary.missing_abstract')} value={s.missing_abstract} tone="warn" />
      </div>
      {s.pending_groups > 0 && (
        <Link to="duplicatas" className="inline-block text-sm text-brand-600 underline">
          {t('summary.review_now')} →
        </Link>
      )}

      <Card>
        <h2 className="mb-3 font-semibold">{t('summary.by_source')}</h2>
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
      </Card>

      {canManage && (
        <Card className="space-y-3">
          <h2 className="font-semibold">{t('summary.actions')}</h2>
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => enrich.mutate()} disabled={busy || enrich.isPending}>
              {t('summary.enrich')}
            </Button>
            <Button
              variant="ghost"
              onClick={() => dedup.mutate()}
              disabled={busy || dedup.isPending}
            >
              {t('summary.dedup')}
            </Button>
          </div>
          <p className="text-xs text-stone-500">{t('summary.enrich_hint')}</p>
          <ErrorText error={enrich.error ?? dedup.error} />
          {failed.map((j) => (
            <p key={j.id} role="alert" className="text-sm text-red-700 dark:text-red-400">
              {t('jobs.failed', { label: t(`jobs.${j.kind}`), error: jobError(t, j.error) })}{' '}
              {j.kind === 'corpus_index' && (
                <Link to="conversa" className="underline">
                  {t('jobs.open_corpus', { tab: t('tabs.corpus') })}
                </Link>
              )}
            </p>
          ))}
        </Card>
      )}
    </div>
  )
}
