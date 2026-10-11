import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useRecentJobs } from '../../api/records'
import { useSnowballInfo, useSourceActions } from '../../api/sources'
import type { ApiSource, Job } from '../../api/types'
import { Button, Card, ErrorText, Field, Input, Select } from '../../components/ui'
import { useProjectContext } from './context'

const API_SOURCES: ApiSource[] = ['pubmed', 'openalex', 'europepmc']
const TARGETS = [
  'pubmed',
  'openalex',
  'europepmc',
  'scopus',
  'wos',
  'embase',
  'cinahl',
  'psycinfo',
  'cochrane',
  'bvs',
] as const

const textarea =
  'w-full rounded-md border border-stone-300 bg-white px-3 py-2 font-mono text-sm dark:border-stone-700 dark:bg-stone-900'

function useLastJob(kind: Job['kind']) {
  const { project } = useProjectContext()
  const jobs = useRecentJobs(project.id)
  return jobs.data?.find((j) => j.kind === kind && j.status === 'done')
}

function LastSearch() {
  const { t } = useTranslation()
  const job = useLastJob('api_search')
  if (!job) return null
  const r = job.result as { source: string; found: number; imported: number; truncated: boolean }
  return (
    <p className="text-sm text-stone-600 dark:text-stone-400">
      {t('sources.last_search', { source: r.source, imported: r.imported, found: r.found })}
      {r.truncated && ` ${t('sources.last_truncated')}`}
    </p>
  )
}

function LastSnowball() {
  const { t } = useTranslation()
  const job = useLastJob('snowball')
  if (!job) return null
  const r = job.result as {
    seeds: number
    matched: number
    already_in_project: number
    not_found?: string[]
    searches: { direction: string; imported: number }[]
  }
  return (
    <div className="space-y-1 rounded-md bg-stone-50 p-3 text-sm dark:bg-stone-900">
      <p className="font-medium">{t('sources.last_snowball')}</p>
      {r.searches.map((s, i) => (
        <p key={i}>{t(`sources.result_${s.direction}`, { count: s.imported })}</p>
      ))}
      <p className="text-stone-500">
        {t('sources.result_matched', { matched: r.matched, seeds: r.seeds })}
        {r.already_in_project > 0 && ` ${t('sources.result_known', { count: r.already_in_project })}`}
      </p>
      {r.not_found && r.not_found.length > 0 && (
        <p className="text-amber-700 dark:text-amber-300">
          {t('sources.result_not_found', { list: r.not_found.join('; ') })}
        </p>
      )}
    </div>
  )
}

function Translate({ query, onUse }: { query: string; onUse: (source: ApiSource, q: string) => void }) {
  const { t } = useTranslation()
  const { project } = useProjectContext()
  const { translate } = useSourceActions(project.id)
  const [target, setTarget] = useState<(typeof TARGETS)[number]>('scopus')
  const result = translate.data
  return (
    <details className="rounded-md border border-stone-200 p-3 dark:border-stone-800">
      <summary className="cursor-pointer text-sm font-medium">{t('sources.translate_title')}</summary>
      <div className="mt-3 space-y-3">
        <p className="text-sm text-stone-500">{t('sources.translate_hint')}</p>
        <div className="flex flex-wrap items-end gap-2">
          <Field label={t('sources.target')}>
            <Select value={target} onChange={(e) => setTarget(e.target.value as typeof target)}>
              {TARGETS.map((x) => (
                <option key={x} value={x}>
                  {t(`sources.db_${x}`)}
                </option>
              ))}
            </Select>
          </Field>
          <Button
            variant="ghost"
            className="border border-stone-300 dark:border-stone-700"
            disabled={!query.trim() || translate.isPending}
            onClick={() => translate.mutate({ query, target })}
          >
            {translate.isPending ? t('sources.translating') : t('sources.translate')}
          </Button>
        </div>
        <ErrorText error={translate.error} />
        {result && (
          <div className="space-y-2">
            <textarea readOnly rows={4} className={textarea} value={result.query} aria-label={t('sources.translated')} />
            {result.notes.length > 0 && (
              <ul className="list-disc pl-5 text-sm text-stone-600 dark:text-stone-400">
                {result.notes.map((n, i) => (
                  <li key={i}>{n}</li>
                ))}
              </ul>
            )}
            <p className="text-xs text-amber-700 dark:text-amber-300">
              {t('sources.translate_review', { model: result.model })}
            </p>
            <div className="flex flex-wrap gap-2">
              <Button variant="ghost" onClick={() => void navigator.clipboard?.writeText(result.query)}>
                {t('sources.copy')}
              </Button>
              {(API_SOURCES as string[]).includes(translate.variables?.target ?? '') && (
                <Button
                  variant="ghost"
                  onClick={() => onUse(translate.variables!.target as ApiSource, result.query)}
                >
                  {t('sources.use_here')}
                </Button>
              )}
            </div>
          </div>
        )}
      </div>
    </details>
  )
}

export function ApiSearchCard() {
  const { t, i18n } = useTranslation()
  const { project } = useProjectContext()
  const { preview, search } = useSourceActions(project.id)
  const [source, setSource] = useState<ApiSource>('pubmed')
  const [query, setQuery] = useState('')
  const [limit, setLimit] = useState(5000)
  const p = preview.data
  const fmt = (n: number) => n.toLocaleString(i18n.language)

  const changeQuery = (q: string) => {
    setQuery(q)
    preview.reset()
    search.reset()
  }

  return (
    <Card className="space-y-4">
      <div>
        <h2 className="font-semibold">{t('sources.title')}</h2>
        <p className="text-sm text-stone-500">{t('sources.hint')}</p>
      </div>
      <div className="grid gap-4 sm:grid-cols-[14rem_1fr]">
        <Field label={t('sources.source')}>
          <Select
            value={source}
            onChange={(e) => {
              setSource(e.target.value as ApiSource)
              preview.reset()
              search.reset()
            }}
          >
            {API_SOURCES.map((s) => (
              <option key={s} value={s}>
                {t(`sources.db_${s}`)}
              </option>
            ))}
          </Select>
        </Field>
        <p className="self-end pb-2 text-xs text-stone-500">{t(`sources.syntax_${source}`)}</p>
      </div>
      <Field label={t('import.query')}>
        <textarea rows={4} className={textarea} value={query} onChange={(e) => changeQuery(e.target.value)} />
      </Field>
      <div className="flex flex-wrap items-end gap-3">
        <Button
          variant="ghost"
          className="border border-stone-300 dark:border-stone-700"
          disabled={!query.trim() || preview.isPending}
          onClick={() => preview.mutate({ source, query })}
        >
          {preview.isPending ? t('sources.counting') : t('sources.count')}
        </Button>
        <Field label={t('sources.limit')}>
          <Input
            type="number"
            min={1}
            max={p?.max}
            className="w-32"
            value={limit}
            onChange={(e) => setLimit(Math.max(1, Number(e.target.value) || 1))}
          />
        </Field>
        <Button
          disabled={!query.trim() || search.isPending || search.isSuccess}
          onClick={() => search.mutate({ source, query, limit })}
        >
          {t('sources.import')}
        </Button>
      </div>
      <ErrorText error={preview.error ?? search.error} />
      {search.isSuccess && (
        <p role="status" className="text-sm text-brand-700 dark:text-brand-100">
          {t('sources.started')}
        </p>
      )}
      {!p && <LastSearch />}
      {p && (
        <div className="space-y-2 rounded-md bg-stone-50 p-3 text-sm dark:bg-stone-900">
          <p className="font-medium">{t('sources.found', { count: p.count, n: fmt(p.count) })}</p>
          {p.count > Math.min(limit, p.max) && (
            <p className="text-amber-700 dark:text-amber-300">
              {t('sources.over_limit', { limit: fmt(Math.min(limit, p.max)) })}
            </p>
          )}
          {p.sample.length > 0 && (
            <>
              <p className="text-stone-500">{t('sources.sample')}</p>
              <ol className="list-decimal space-y-1 pl-5">
                {p.sample.map((r, i) => (
                  <li key={i}>
                    <span className="font-medium">{r.title || t('records.no_title')}</span>
                    <span className="text-stone-500">
                      {' '}
                      · {[r.authors[0], r.year, r.journal].filter(Boolean).join(' · ')}
                    </span>
                  </li>
                ))}
              </ol>
            </>
          )}
        </div>
      )}
      <Translate
        query={query}
        onUse={(s, q) => {
          setSource(s)
          changeQuery(q)
        }}
      />
    </Card>
  )
}

export function SnowballCard() {
  const { t } = useTranslation()
  const { project } = useProjectContext()
  const info = useSnowballInfo(project.id)
  const { snowball } = useSourceActions(project.id)
  const [direction, setDirection] = useState<'both' | 'backward' | 'forward'>('both')
  const included = info.data?.included ?? 0
  return (
    <Card className="space-y-4">
      <div>
        <h2 className="font-semibold">{t('sources.snowball_title')}</h2>
        <p className="text-sm text-stone-500">{t('sources.snowball_hint')}</p>
      </div>
      <p className="text-sm">
        {included > 0 ? t('sources.seeds', { count: included }) : t('sources.no_seeds')}
      </p>
      <fieldset className="space-y-2">
        <legend className="sr-only">{t('sources.direction')}</legend>
        {(['both', 'backward', 'forward'] as const).map((d) => (
          <label key={d} className="flex items-start gap-2 text-sm">
            <input
              type="radio"
              name="snowball-direction"
              className="mt-1 accent-brand-600"
              checked={direction === d}
              onChange={() => setDirection(d)}
            />
            <span>
              <span className="font-medium">{t(`sources.dir_${d}`)}</span>
              <span className="block text-xs text-stone-500">{t(`sources.dir_${d}_hint`)}</span>
            </span>
          </label>
        ))}
      </fieldset>
      <ErrorText error={snowball.error} />
      {snowball.isSuccess && (
        <p role="status" className="text-sm text-brand-700 dark:text-brand-100">
          {t('sources.started')}
        </p>
      )}
      <Button
        disabled={included === 0 || snowball.isPending || info.data?.enabled === false}
        onClick={() => snowball.mutate({ direction })}
      >
        {t('sources.snowball_start')}
      </Button>
      <LastSnowball />
    </Card>
  )
}
