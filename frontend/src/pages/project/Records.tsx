import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useRecords, type RecordFilter } from '../../api/records'
import { citationLine } from '../../components/citation'
import { Badge, RecordDetails } from '../../components/RecordView'
import { Button, Card, ErrorText, Input, Select } from '../../components/ui'
import { useProjectContext } from './context'

const FILTERS: RecordFilter[] = ['all', 'unique', 'duplicates', 'missing_abstract']

export default function Records() {
  const { t } = useTranslation()
  const { project } = useProjectContext()
  const [input, setInput] = useState('')
  const [q, setQ] = useState('')
  const [filter, setFilter] = useState<RecordFilter>('unique')
  const [page, setPage] = useState(1)
  const [open, setOpen] = useState<string | null>(null)

  // Espera a pessoa parar de digitar antes de buscar
  useEffect(() => {
    const id = setTimeout(() => {
      setQ(input)
      setPage(1)
    }, 300)
    return () => clearTimeout(id)
  }, [input])

  const { data, error, isFetching } = useRecords(project.id, { q, filter, page })
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-2 sm:flex-row">
        <Input
          type="search"
          placeholder={t('records.search')}
          aria-label={t('records.search')}
          value={input}
          onChange={(e) => setInput(e.target.value)}
        />
        <Select
          aria-label={t('records.filter')}
          className="sm:w-56"
          value={filter}
          onChange={(e) => {
            setFilter(e.target.value as RecordFilter)
            setPage(1)
          }}
        >
          {FILTERS.map((f) => (
            <option key={f} value={f}>
              {t(`records.filter_${f}`)}
            </option>
          ))}
        </Select>
      </div>
      <ErrorText error={error} />
      {data && (
        <p className={`text-sm text-stone-500 ${isFetching ? 'opacity-60' : ''}`}>
          {t('records.count', { count: data.total })}
        </p>
      )}
      {data?.items.length === 0 && <p className="text-stone-500">{t('records.none')}</p>}
      <ul className="space-y-2">
        {data?.items.map((r) => (
          <li key={r.id}>
            <Card className="p-4">
              <button
                type="button"
                className="w-full text-left"
                aria-expanded={open === r.id}
                onClick={() => setOpen(open === r.id ? null : r.id)}
              >
                <p className="font-medium">{r.title || t('records.no_title')}</p>
                <p className="mt-1 text-sm text-stone-500">{citationLine(r)}</p>
                <p className="mt-1 space-x-1">
                  {r.is_duplicate && <Badge tone="amber">{t('records.duplicate_badge')}</Badge>}
                  {Object.keys(r.enriched).length > 0 && (
                    <Badge tone="brand">{t('records.enriched_badge')}</Badge>
                  )}
                </p>
              </button>
              {open === r.id && (
                <div className="mt-3 border-t border-stone-100 pt-3 dark:border-stone-800">
                  <RecordDetails r={r} />
                </div>
              )}
            </Card>
          </li>
        ))}
      </ul>
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
