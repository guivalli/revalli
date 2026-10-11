import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useDuplicates, useRecordActions, useSearches } from '../../api/records'
import type { DuplicateGroup, RecordItem } from '../../api/types'
import { RecordLinks } from '../../components/RecordView'
import { Button, Card, ErrorText } from '../../components/ui'
import { useProjectContext } from './context'

type FieldKey = 'source' | 'title' | 'authors' | 'year' | 'journal' | 'doi' | 'pmid' | 'abstract'
const FIELDS: FieldKey[] = ['source', 'title', 'authors', 'year', 'journal', 'doi', 'pmid', 'abstract']

function GroupCard({
  projectId,
  group,
  canManage,
  sourceName,
}: {
  projectId: string
  group: DuplicateGroup
  canManage: boolean
  sourceName: (r: RecordItem) => string
}) {
  const { t } = useTranslation()
  const { confirm, reject, split } = useRecordActions(projectId)
  const value = (r: RecordItem, f: FieldKey): string => {
    if (f === 'source') return sourceName(r)
    if (f === 'authors') return r.authors.join('; ')
    if (f === 'year') return r.year ? String(r.year) : ''
    return (r[f] as string | null) ?? ''
  }
  const differs = (f: FieldKey) =>
    new Set(group.records.map((r) => value(r, f).toLowerCase().trim())).size > 1
  const method =
    group.method === 'title'
      ? t('dups.method_title', { score: group.score })
      : t(`dups.method_${group.method}`)
  const busy = confirm.isPending || reject.isPending || split.isPending

  return (
    <Card className="space-y-3 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-sm text-stone-500">{method}</span>
        {canManage && group.status === 'pending' && (
          <Button variant="ghost" disabled={busy} onClick={() => reject.mutate(group.id)}>
            {t('dups.none_dup')}
          </Button>
        )}
      </div>
      <div className="grid gap-3" style={{ gridTemplateColumns: `repeat(${group.records.length}, minmax(14rem, 1fr))` }}>
        {group.records.map((r) => {
          const isPrimary = group.status === 'confirmed' && r.id === group.primary_record_id
          return (
            <div
              key={r.id}
              className={`space-y-2 rounded-md border p-3 text-sm ${isPrimary ? 'border-brand-500' : 'border-stone-200 dark:border-stone-800'}`}
            >
              <dl className="space-y-1">
                {FIELDS.map((f) => {
                  const v = value(r, f)
                  return (
                    <div
                      key={f}
                      className={`rounded px-1 ${differs(f) ? 'bg-amber-50 dark:bg-amber-950' : ''}`}
                    >
                      <dt className="text-xs text-stone-500">{t(`dups.fields.${f}`)}</dt>
                      <dd className={f === 'abstract' ? 'line-clamp-4' : 'break-words'}>
                        {v || '—'}
                      </dd>
                    </div>
                  )
                })}
              </dl>
              <RecordLinks r={r} />
              {canManage && (
                <div className="flex flex-wrap gap-1 pt-1">
                  {isPrimary ? (
                    <span className="px-3 py-2 text-sm font-medium text-brand-700">{t('dups.kept')}</span>
                  ) : (
                    <Button
                      disabled={busy}
                      onClick={() => confirm.mutate({ gid: group.id, primary: r.id })}
                    >
                      {t('dups.keep')}
                    </Button>
                  )}
                  <Button
                    variant="ghost"
                    disabled={busy}
                    onClick={() => split.mutate({ gid: group.id, record: r.id })}
                  >
                    {t('dups.not_dup')}
                  </Button>
                </div>
              )}
            </div>
          )
        })}
      </div>
      <ErrorText error={confirm.error ?? reject.error ?? split.error} />
    </Card>
  )
}

export default function Duplicates() {
  const { t } = useTranslation()
  const { project, canManage } = useProjectContext()
  const [status, setStatus] = useState<'pending' | 'confirmed'>('pending')
  const [page, setPage] = useState(1)
  const { data, error } = useDuplicates(project.id, status, page)
  const searches = useSearches(project.id)
  const sourceName = (r: RecordItem) =>
    searches.data?.find((s) => s.id === r.search_id)?.source ?? ''
  const pages = data ? Math.max(1, Math.ceil(data.total / 10)) : 1

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        {(['pending', 'confirmed'] as const).map((s) => (
          <Button
            key={s}
            variant={status === s ? 'primary' : 'ghost'}
            onClick={() => {
              setStatus(s)
              setPage(1)
            }}
          >
            {t(`dups.${s}`)}
          </Button>
        ))}
      </div>
      {canManage && status === 'pending' && (data?.total ?? 0) > 0 && (
        <p className="text-sm text-stone-500">{t('dups.explain')}</p>
      )}
      <ErrorText error={error} />
      {data?.total === 0 && (
        <p className="text-stone-500">{t(status === 'pending' ? 'dups.none_pending' : 'dups.none_confirmed')}</p>
      )}
      <div className="space-y-4 overflow-x-auto">
        {data?.items.map((g) => (
          <GroupCard key={g.id} projectId={project.id} group={g} canManage={canManage} sourceName={sourceName} />
        ))}
      </div>
      {pages > 1 && (
        <div className="flex items-center justify-between">
          <Button variant="ghost" disabled={page <= 1} onClick={() => setPage(page - 1)}>
            ← {t('records.prev')}
          </Button>
          <span className="text-sm text-stone-500">{t('records.page', { page, pages })}</span>
          <Button variant="ghost" disabled={page >= pages} onClick={() => setPage(page + 1)}>
            {t('records.next')} →
          </Button>
        </div>
      )}
    </div>
  )
}
