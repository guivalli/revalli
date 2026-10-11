import { useDeferredValue, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useStudies, useStudyActions, useStudyCandidates, useStudySuggestions } from '../../api/files'
import type { StudyRecord } from '../../api/types'
import { Button, Card, ErrorText, Input } from '../../components/ui'
import { useProjectContext } from './context'

function cite(r: { authors: string[]; year: number | null }) {
  const first = (r.authors[0] ?? '').split(',')[0].trim()
  return [first + (r.authors.length > 1 ? ' et al.' : ''), r.year].filter(Boolean).join(', ')
}

function RecordLine({ r }: { r: Pick<StudyRecord, 'title' | 'authors' | 'year'> }) {
  const { t } = useTranslation()
  return (
    <span>
      <span className="text-stone-500">{cite(r)}</span>
      {cite(r) && ' · '}
      {r.title || t('records.no_title')}
    </span>
  )
}

export function StudiesSection() {
  const { t } = useTranslation()
  const { project } = useProjectContext()
  const canEdit = project.my_role !== 'observer'
  const list = useStudies(project.id)
  const suggestions = useStudySuggestions(project.id)
  const { create, update, removeReport, remove } = useStudyActions(project.id)
  const [q, setQ] = useState('')
  const query = useDeferredValue(q.trim())
  const candidates = useStudyCandidates(project.id, query, canEdit && query.length >= 2)
  const [picked, setPicked] = useState<Record<string, string>>({})
  const studies = list.data ?? []
  const sugg = suggestions.data ?? []
  const error = create.error ?? update.error ?? removeReport.error ?? remove.error

  const toggle = (id: string, title: string) =>
    setPicked((p) => {
      const next = { ...p }
      if (id in next) delete next[id]
      else next[id] = title
      return next
    })

  return (
    <Card className="space-y-5">
      <div>
        <h2 className="text-lg font-semibold">{t('studies.title')}</h2>
        <p className="text-sm text-stone-500">{t('studies.hint')}</p>
      </div>
      <ErrorText error={error} />

      {sugg.length > 0 && (
        <section className="space-y-2" aria-label={t('studies.suggestions')}>
          <h3 className="text-sm font-medium">{t('studies.suggestions')}</h3>
          <ul className="space-y-2">
            {sugg.map((s) => (
              <li
                key={s.key + s.records.map((r) => r.id).join()}
                className="flex flex-wrap items-start justify-between gap-3 rounded-md bg-amber-50 p-3 text-sm dark:bg-stone-800"
              >
                <div className="min-w-0 flex-1 space-y-1">
                  <p className="font-mono text-xs text-amber-800 dark:text-amber-300">{s.key}</p>
                  {s.records.map((r) => (
                    <p key={r.id} className="truncate">
                      <RecordLine r={r} />
                    </p>
                  ))}
                </div>
                {canEdit && (
                  <Button
                    variant="ghost"
                    className="border border-stone-300 dark:border-stone-700"
                    disabled={create.isPending}
                    onClick={() => create.mutate({ record_ids: s.records.map((r) => r.id) })}
                  >
                    {t('studies.group')}
                  </Button>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      {studies.length > 0 ? (
        <ul className="space-y-3">
          {studies.map((s) => (
            <li key={s.id} className="space-y-2 rounded-md border border-stone-200 p-3 dark:border-stone-800">
              <div className="flex flex-wrap items-center gap-2">
                {canEdit ? (
                  <Input
                    key={s.label}
                    aria-label={t('studies.label')}
                    className="max-w-xs"
                    defaultValue={s.label}
                    onBlur={(e) => {
                      const label = e.target.value.trim()
                      if (label && label !== s.label) update.mutate({ sid: s.id, label })
                    }}
                  />
                ) : (
                  <span className="font-medium">{s.label}</span>
                )}
                <span className="text-sm text-stone-500">{t('studies.reports', { count: s.reports.length })}</span>
                {canEdit && (
                  <Button
                    variant="danger"
                    className="ml-auto"
                    onClick={() => window.confirm(t('studies.ungroup_confirm')) && remove.mutate(s.id)}
                  >
                    {t('studies.ungroup')}
                  </Button>
                )}
              </div>
              <ul className="space-y-1 text-sm">
                {s.reports.map((r) => (
                  <li key={r.id} className="flex items-start gap-2">
                    <span className="min-w-0 flex-1">
                      <RecordLine r={r} />
                      {r.state && (
                        <span className="ml-2 text-xs text-stone-500">({t(`state.${r.state}`)})</span>
                      )}
                    </span>
                    {r.is_primary ? (
                      <span className="shrink-0 rounded bg-brand-50 px-2 py-0.5 text-xs text-brand-700 dark:bg-stone-800 dark:text-brand-100">
                        {t('studies.primary')}
                      </span>
                    ) : (
                      canEdit && (
                        <button
                          type="button"
                          className="shrink-0 text-xs text-brand-600 hover:underline"
                          onClick={() => update.mutate({ sid: s.id, primary_record_id: r.id })}
                        >
                          {t('studies.make_primary')}
                        </button>
                      )
                    )}
                    {canEdit && (
                      <button
                        type="button"
                        aria-label={t('studies.remove_report')}
                        title={t('studies.remove_report')}
                        className="shrink-0 px-1 text-stone-400 hover:text-red-600"
                        onClick={() => removeReport.mutate({ sid: s.id, rid: r.id })}
                      >
                        ×
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      ) : (
        !sugg.length && <p className="text-sm text-stone-500">{t('studies.none')}</p>
      )}

      {canEdit && (
        <section className="space-y-2" aria-label={t('studies.new')}>
          <h3 className="text-sm font-medium">{t('studies.new')}</h3>
          <Input
            type="search"
            aria-label={t('studies.search')}
            placeholder={t('studies.search')}
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          {query.length >= 2 && (
            <ul className="max-h-64 space-y-1 overflow-auto text-sm">
              {(candidates.data ?? []).map((c) => (
                <li key={c.id}>
                  <label className="flex cursor-pointer items-start gap-2">
                    <input
                      type="checkbox"
                      className="mt-1"
                      checked={c.id in picked}
                      onChange={() => toggle(c.id, `${cite(c)} · ${c.title}`)}
                    />
                    <span>
                      <RecordLine r={c} />
                      {c.study_id && <span className="ml-2 text-xs text-stone-500">({t('studies.in_group')})</span>}
                    </span>
                  </label>
                </li>
              ))}
              {candidates.data?.length === 0 && <li className="text-stone-500">{t('studies.no_match')}</li>}
            </ul>
          )}
          {Object.keys(picked).length > 0 && (
            <div className="space-y-2 rounded-md bg-stone-50 p-3 text-sm dark:bg-stone-800">
              <ul className="space-y-1">
                {Object.entries(picked).map(([id, title]) => (
                  <li key={id} className="flex items-start gap-2">
                    <span className="min-w-0 flex-1 truncate">{title}</span>
                    <button type="button" className="text-stone-400 hover:text-red-600" onClick={() => toggle(id, title)}>
                      ×
                    </button>
                  </li>
                ))}
              </ul>
              <Button
                disabled={Object.keys(picked).length < 2 || create.isPending}
                onClick={() =>
                  create.mutate(
                    { record_ids: Object.keys(picked) },
                    {
                      onSuccess: () => {
                        setPicked({})
                        setQ('')
                      },
                    },
                  )
                }
              >
                {t('studies.group_selected', { count: Object.keys(picked).length })}
              </Button>
            </div>
          )}
        </section>
      )}
    </Card>
  )
}
