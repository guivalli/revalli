import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useWatchActions, useWatches } from '../../api/watches'
import type { ApiSource, Watch, WatchInput } from '../../api/types'
import { Button, Card, ErrorText, Field, Input, Select } from '../../components/ui'
import { useProjectContext } from './context'

const SOURCES: ApiSource[] = ['pubmed', 'openalex', 'europepmc']
const textarea =
  'w-full rounded-md border border-stone-300 bg-white px-3 py-2 font-mono text-sm dark:border-stone-700 dark:bg-stone-900'

const EMPTY: WatchInput = {
  kind: 'api_search',
  name: '',
  source: 'pubmed',
  query: '',
  url: '',
  secret: '',
  clear_secret: false,
  every_days: 7,
  enabled: true,
}

function WatchRow({ w, canManage }: { w: Watch; canManage: boolean }) {
  const { t, i18n } = useTranslation()
  const { project } = useProjectContext()
  const { run, remove, update } = useWatchActions(project.id)
  const when = (iso: string | null) => (iso ? new Date(iso).toLocaleString(i18n.language) : '–')
  const input = (): WatchInput => ({
    kind: w.kind,
    name: w.name,
    source: w.source,
    query: w.query,
    url: w.url,
    secret: '',
    clear_secret: false,
    every_days: w.every_days,
    enabled: w.enabled,
  })
  return (
    <li className="space-y-1 py-3 text-sm">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-medium">
            {w.name || (w.kind === 'api_search' ? t(`sources.db_${w.source}`) : w.url)}
            <span className="ml-2 rounded-full bg-sky-50 px-2 py-0.5 text-xs font-normal text-sky-700 dark:bg-sky-950 dark:text-sky-300">
              {t(`watches.kind_${w.kind}`)}
            </span>
            {!w.enabled && (
              <span className="ml-2 text-xs font-normal text-stone-500">{t('watches.paused')}</span>
            )}
          </p>
          <p className="break-all font-mono text-xs text-stone-500">
            {w.kind === 'api_search' ? w.query : w.url}
          </p>
        </div>
        {canManage && (
          <div className="flex gap-1">
            <Button variant="ghost" disabled={run.isPending} onClick={() => run.mutate(w.id)}>
              {run.isPending ? t('watches.running') : t('watches.run_now')}
            </Button>
            <Button
              variant="ghost"
              onClick={() => update.mutate({ id: w.id, body: { ...input(), enabled: !w.enabled } })}
            >
              {w.enabled ? t('watches.pause') : t('watches.resume')}
            </Button>
            <Button variant="danger" onClick={() => remove.mutate(w.id)}>
              {t('watches.remove')}
            </Button>
          </div>
        )}
      </div>
      <p className="text-xs text-stone-500">
        {t('watches.every', { count: w.every_days })} · {t('watches.last_run', { date: when(w.last_run_at) })}
        {w.enabled && ` · ${t('watches.next_run', { date: when(w.next_run_at) })}`}
      </p>
      {w.last_status === 'ok' && (
        <p className={w.last_new > 0 ? 'text-brand-700 dark:text-brand-100' : 'text-stone-500'}>
          {t('watches.last_result', { new: w.last_new, found: w.last_found, total: w.total_new })}
        </p>
      )}
      {w.last_status === 'error' && (
        <p role="alert" className="text-red-700 dark:text-red-400">
          {t('watches.last_error')}: {t(`watches.error_${w.last_error}`, { defaultValue: w.last_error })}
        </p>
      )}
      <ErrorText error={run.error ?? remove.error ?? update.error} />
    </li>
  )
}

export function WatchesCard() {
  const { t } = useTranslation()
  const { project, canManage } = useProjectContext()
  const watches = useWatches(project.id)
  const { create } = useWatchActions(project.id)
  const [form, setForm] = useState<WatchInput>(EMPTY)
  const list = watches.data ?? []
  const valid = form.kind === 'api_search' ? form.query.trim() !== '' : form.url.trim() !== ''

  return (
    <Card className="space-y-4">
      <div>
        <h2 className="font-semibold">{t('watches.title')}</h2>
        <p className="text-sm text-stone-500">{t('watches.hint')}</p>
      </div>
      {list.length === 0 && <p className="text-sm text-stone-500">{t('watches.none')}</p>}
      <ul className="divide-y divide-stone-200 dark:divide-stone-800">
        {list.map((w) => (
          <WatchRow key={w.id} w={w} canManage={canManage} />
        ))}
      </ul>
      {canManage && (
        <div className="space-y-3 border-t border-stone-200 pt-4 dark:border-stone-800">
          <p className="text-sm font-medium">{t('watches.add')}</p>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label={t('watches.kind')}>
              <Select
                value={form.kind}
                onChange={(e) => setForm({ ...form, kind: e.target.value as WatchInput['kind'] })}
              >
                <option value="api_search">{t('watches.kind_api_search')}</option>
                <option value="feed_url">{t('watches.kind_feed_url')}</option>
              </Select>
            </Field>
            <Field label={t('watches.name')}>
              <Input value={form.name} maxLength={200} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </Field>
            <Field label={t('watches.every_label')}>
              <Input
                type="number"
                min={1}
                max={365}
                value={form.every_days}
                onChange={(e) => setForm({ ...form, every_days: Math.max(1, Number(e.target.value) || 1) })}
              />
            </Field>
          </div>
          {form.kind === 'api_search' ? (
            <>
              <Field label={t('sources.source')}>
                <Select value={form.source} onChange={(e) => setForm({ ...form, source: e.target.value })}>
                  {SOURCES.map((s) => (
                    <option key={s} value={s}>
                      {t(`sources.db_${s}`)}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label={t('import.query')}>
                <textarea
                  rows={3}
                  className={textarea}
                  value={form.query}
                  onChange={(e) => setForm({ ...form, query: e.target.value })}
                />
              </Field>
            </>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label={t('watches.url')} hint={t('watches.url_hint')}>
                <Input value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} />
              </Field>
              <Field label={t('watches.secret')} hint={t('watches.secret_hint')}>
                <Input
                  type="password"
                  autoComplete="off"
                  value={form.secret}
                  onChange={(e) => setForm({ ...form, secret: e.target.value })}
                />
              </Field>
            </div>
          )}
          <ErrorText error={create.error} />
          <Button
            disabled={!valid || create.isPending}
            onClick={() => create.mutate(form, { onSuccess: () => setForm(EMPTY) })}
          >
            {t('watches.create')}
          </Button>
        </div>
      )}
    </Card>
  )
}
