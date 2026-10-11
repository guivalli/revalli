import { useRef, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Navigate } from 'react-router-dom'
import { useRecordActions, useSearches } from '../../api/records'
import type { Search } from '../../api/types'
import { Button, Card, ErrorText, Field, Input, Select } from '../../components/ui'
import { useProjectContext } from './context'
import { ApiSearchCard, SnowballCard } from './SourceSearch'

const SOURCES = [
  'PubMed',
  'Scopus',
  'Web of Science',
  'Embase',
  'LILACS',
  'BVS',
  'SciELO',
  'CINAHL',
  'PsycINFO',
  'Cochrane Library',
]
const FORMATS = ['ris', 'medline', 'pubmed_xml', 'bibtex', 'wos', 'csv']

const textarea =
  'w-full rounded-md border border-stone-300 bg-white px-3 py-2 font-mono text-sm dark:border-stone-700 dark:bg-stone-900'

function SearchRow({ s, onDelete }: { s: Search; onDelete: () => void }) {
  const { t } = useTranslation()
  const [showQuery, setShowQuery] = useState(false)
  const mismatch = s.reported_count != null && s.reported_count !== s.imported_count
  return (
    <li className="space-y-2 py-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-medium">
            {s.source}
            {s.method !== 'database' && (
              <span className="ml-2 rounded-full bg-sky-50 px-2 py-0.5 text-xs font-normal text-sky-700 dark:bg-sky-950 dark:text-sky-300">
                {t(`import.method_${s.method}`)}
              </span>
            )}
          </p>
          <p className="text-sm text-stone-500">
            {s.file_format === 'api' ? t('import.via_api') : s.file_name} · {t('import.imported')}: {s.imported_count}
            {s.reported_count != null && ` · ${t('import.reported')}: ${s.reported_count}`}
            {s.searched_on && ` · ${t('import.date')}: ${new Date(s.searched_on + 'T00:00').toLocaleDateString()}`}
          </p>
          {mismatch && (
            <p className="text-xs text-amber-700 dark:text-amber-300">
              {t(s.file_format === 'api' ? 'import.mismatch_api' : 'import.mismatch', {
                reported: s.reported_count,
                imported: s.imported_count,
              })}
            </p>
          )}
        </div>
        <div className="flex gap-1">
          {s.query && (
            <Button variant="ghost" onClick={() => setShowQuery(!showQuery)}>
              {showQuery ? t('import.hide_query') : t('import.edit_query')}
            </Button>
          )}
          <Button variant="danger" onClick={onDelete}>
            {t('import.delete')}
          </Button>
        </div>
      </div>
      {showQuery && (
        <pre className="whitespace-pre-wrap rounded bg-stone-100 p-3 text-xs dark:bg-stone-800">
          {s.query}
        </pre>
      )}
    </li>
  )
}

export default function Import() {
  const { t } = useTranslation()
  const { project, canManage } = useProjectContext()
  const searches = useSearches(project.id)
  const { importFile, deleteSearch } = useRecordActions(project.id)
  const fileRef = useRef<HTMLInputElement>(null)
  const [form, setForm] = useState(() => ({
    source: '',
    query: '',
    searched_on: new Date().toISOString().slice(0, 10),
    reported_count: '',
    notes: '',
    file_format: '',
  }))

  if (!canManage) return <Navigate to=".." replace />

  const submit = (e: FormEvent) => {
    e.preventDefault()
    const file = fileRef.current?.files?.[0]
    if (!file) return
    const data = new FormData()
    data.set('file', file)
    for (const [k, v] of Object.entries(form)) if (v) data.set(k, v)
    importFile.mutate(data, {
      onSuccess: () => {
        if (fileRef.current) fileRef.current.value = ''
        setForm((f) => ({ ...f, query: '', reported_count: '', notes: '' }))
      },
    })
  }

  const remove = (s: Search) => {
    if (window.confirm(t('import.delete_confirm', { count: s.imported_count })))
      deleteSearch.mutate(s.id)
  }

  return (
    <div className="space-y-6">
      <Card>
        <form onSubmit={submit} className="space-y-4">
          <h2 className="font-semibold">{t('import.title')}</h2>
          <Field label={t('import.file')} hint={t('import.file_hint')}>
            <Input
              ref={fileRef}
              required
              type="file"
              accept=".ris,.txt,.nbib,.xml,.bib,.csv,.tsv"
              className="file:mr-3 file:rounded file:border-0 file:bg-brand-50 file:px-3 file:py-1 file:text-brand-700"
            />
          </Field>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label={t('import.source')}>
              <Input
                required
                list="revalli-sources"
                placeholder={t('import.source_placeholder')}
                value={form.source}
                onChange={(e) => setForm({ ...form, source: e.target.value })}
              />
              <datalist id="revalli-sources">
                {SOURCES.map((s) => (
                  <option key={s} value={s} />
                ))}
              </datalist>
            </Field>
            <Field label={t('import.searched_on')}>
              <Input
                type="date"
                value={form.searched_on}
                onChange={(e) => setForm({ ...form, searched_on: e.target.value })}
              />
            </Field>
            <Field label={t('import.reported_count')}>
              <Input
                type="number"
                min={0}
                value={form.reported_count}
                onChange={(e) => setForm({ ...form, reported_count: e.target.value })}
              />
            </Field>
          </div>
          <Field label={t('import.query')} hint={t('import.query_hint')}>
            <textarea
              rows={4}
              className={textarea}
              value={form.query}
              onChange={(e) => setForm({ ...form, query: e.target.value })}
            />
          </Field>
          <div className="grid gap-4 sm:grid-cols-[1fr_14rem]">
            <Field label={t('import.notes')}>
              <Input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
            </Field>
            <Field label={t('import.format')}>
              <Select
                value={form.file_format}
                onChange={(e) => setForm({ ...form, file_format: e.target.value })}
              >
                <option value="">{t('import.format_auto')}</option>
                {FORMATS.map((f) => (
                  <option key={f} value={f}>
                    {f}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
          <ErrorText error={importFile.error} />
          {importFile.data && (
            <p role="status" className="text-sm text-brand-700 dark:text-brand-100">
              {t('import.done', { count: importFile.data.imported })}
            </p>
          )}
          <Button type="submit" disabled={importFile.isPending}>
            {t('import.submit')}
          </Button>
        </form>
      </Card>

      <ApiSearchCard />
      <SnowballCard />

      <Card>
        <h2 className="font-semibold">{t('import.history')}</h2>
        <ErrorText error={deleteSearch.error} />
        {searches.data?.length === 0 && <p className="mt-2 text-sm text-stone-500">{t('import.none')}</p>}
        <ul className="divide-y divide-stone-200 dark:divide-stone-800">
          {searches.data?.map((s) => (
            <SearchRow key={s.id} s={s} onDelete={() => remove(s)} />
          ))}
        </ul>
      </Card>
    </div>
  )
}
