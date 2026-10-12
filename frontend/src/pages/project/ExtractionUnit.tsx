import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'
import { useComparison, useExtractionActions, useUnit } from '../../api/extraction'
import { useScreeningSettings } from '../../api/screening'
import type { ExtractionT, FieldDef, FieldValue, QuoteT, UnitDetailT } from '../../api/types'
import { FieldInput } from '../../components/FormField'
import { isVisible, useFormatValue, type Values } from '../../lib/fields'
import { FullTextPanel } from '../../components/FullTextPanel'
import { Button, Card, ErrorText } from '../../components/ui'
import { useProjectContext } from './context'

type Focus = { page: number; text: string; fileId: string | null }

function QuoteLine({ q, onShow }: { q: QuoteT; onShow: (f: Focus) => void }) {
  const { t } = useTranslation()
  return (
    <span className="block text-xs">
      <span className={q.verified ? 'text-emerald-700 dark:text-emerald-400' : 'text-amber-700 dark:text-amber-300'}>
        {q.verified ? t('extraction.quote_verified', { page: q.page }) : t('extraction.quote_unverified')}
      </span>{' '}
      <q className="italic text-stone-600 dark:text-stone-400">{q.text}</q>
      {q.page && (
        <button
          type="button"
          className="ml-2 text-brand-600 dark:text-brand-300 hover:underline"
          onClick={() => onShow({ page: q.page!, text: q.text, fileId: q.file_id })}
        >
          {t('extraction.show_in_pdf')}
        </button>
      )}
    </span>
  )
}

function FieldBlock({
  f,
  values,
  suggested,
  ai,
  onChange,
  onUseAI,
  onShow,
  disabled,
}: {
  f: FieldDef
  values: Values
  suggested: Record<string, string>
  ai: ExtractionT | null
  onChange: (v: FieldValue) => void
  onUseAI: () => void
  onShow: (f: Focus) => void
  disabled?: boolean
}) {
  const { t } = useTranslation()
  const format = useFormatValue()
  if (f.type === 'section')
    return <h3 className="border-b border-stone-200 pt-3 text-base font-semibold dark:border-stone-800">{f.label}</h3>
  const aiValue = ai?.values[f.id]
  const quote = ai?.quotes[f.id]
  return (
    <div className="space-y-1.5">
      <label htmlFor={`f-${f.id}`} id={`f-${f.id}-label`} className="block text-sm font-medium">
        {f.label}
        {f.required && <span className="text-red-600"> *</span>}
      </label>
      {f.help && <p className="text-xs text-stone-500">{f.help}</p>}
      <FieldInput f={f} value={values[f.id]} suggested={suggested[f.id]} onChange={onChange} disabled={disabled} />
      {aiValue !== undefined && aiValue !== null && (
        <div className="rounded-md bg-violet-50 px-2 py-1.5 text-sm dark:bg-stone-800">
          <span className="font-medium text-violet-800 dark:text-violet-300">{t('extraction.ai_says')}</span>{' '}
          {format(f, aiValue)}
          {!disabled && (
            <button type="button" className="ml-2 text-brand-600 dark:text-brand-300 hover:underline" onClick={onUseAI}>
              {t('extraction.use')}
            </button>
          )}
          {quote && <QuoteLine q={quote} onShow={onShow} />}
        </div>
      )}
    </div>
  )
}

function MyExtraction({ detail, onShow }: { detail: UnitDetailT; onShow: (f: Focus) => void }) {
  const { t } = useTranslation()
  const { project } = useProjectContext()
  const { formId = '', recordId = '' } = useParams()
  const { saveMine } = useExtractionActions(project.id, formId, recordId)
  const [values, setValues] = useState<Values>(detail.mine?.values ?? {})
  const [quotes, setQuotes] = useState<Record<string, QuoteT>>(detail.mine?.quotes ?? {})
  const [dirty, setDirty] = useState(false)
  const canExtract = project.my_role !== 'observer' && project.my_role !== 'arbitrator'
  const fields = detail.form.fields
  const suggested = saveMine.data?.suggested ?? detail.mine?.suggested ?? {}
  const status = saveMine.data?.status ?? detail.mine?.status

  const set = (id: string, v: FieldValue) => {
    setValues((all) => ({ ...all, [id]: v }))
    setDirty(true)
  }
  const save = (st: 'draft' | 'done') =>
    saveMine.mutate(
      { values, quotes, status: st },
      {
        onSuccess: (e) => {
          setValues(e.values)
          setDirty(false)
        },
      },
    )

  return (
    <Card className="space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-lg font-semibold">{t('extraction.my_extraction')}</h2>
        <span className="text-sm text-stone-500">
          {dirty ? t('extraction.unsaved') : status ? t(`extraction.mine_${status}`) : t('extraction.mine_none')}
        </span>
      </div>
      {detail.ai && <p className="text-sm text-stone-500">{t('extraction.ai_hint')}</p>}
      <div className="space-y-4">
        {fields
          .filter((f) => isVisible(f, values))
          .map((f) => (
            <FieldBlock
              key={f.id}
              f={f}
              values={values}
              suggested={suggested}
              ai={detail.ai}
              disabled={!canExtract}
              onChange={(v) => set(f.id, v)}
              onShow={onShow}
              onUseAI={() => {
                set(f.id, detail.ai!.values[f.id])
                const q = detail.ai!.quotes[f.id]
                if (q) setQuotes((all) => ({ ...all, [f.id]: q }))
              }}
            />
          ))}
      </div>
      {canExtract && (
        <div className="sticky bottom-0 -mx-6 -mb-6 flex flex-wrap items-center gap-3 border-t border-stone-200 bg-white/95 px-6 py-3 dark:border-stone-800 dark:bg-stone-900/95">
          <Button variant="ghost" className="border border-stone-300 dark:border-stone-700" disabled={saveMine.isPending} onClick={() => save('draft')}>
            {t('extraction.save_draft')}
          </Button>
          <Button disabled={saveMine.isPending} onClick={() => save('done')}>
            {t('extraction.finish')}
          </Button>
          {saveMine.isSuccess && !dirty && <span className="text-sm text-stone-500">{t('extraction.saved')}</span>}
          <ErrorText error={saveMine.error} />
        </div>
      )}
    </Card>
  )
}

function Compare({ detail }: { detail: UnitDetailT }) {
  const { t } = useTranslation()
  const { project } = useProjectContext()
  const { formId = '', recordId = '' } = useParams()
  const cmp = useComparison(project.id, formId, recordId, true)
  const { saveConsensus, removeConsensus } = useExtractionActions(project.id, formId, recordId)
  const format = useFormatValue()
  const [cons, setCons] = useState<Values | null>(null)
  if (!cmp.data) return <p className="text-sm text-stone-500">{t('app.loading')}</p>
  const exts = cmp.data.extractions
  const byId = Object.fromEntries(detail.form.fields.map((f) => [f.id, f]))
  const current: Values = cons ?? detail.consensus?.values ?? cmp.data.agreed_values
  const who = (e: ExtractionT) => (e.kind === 'ai' ? t('extraction.ai') : e.user_name)

  return (
    <Card className="space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-lg font-semibold">{t('extraction.compare')}</h2>
        <span className="text-sm text-stone-500">
          {t('extraction.disagreements', { count: cmp.data.fields.filter((r) => !r.agree).length })}
        </span>
      </div>
      <p className="text-sm text-stone-500">{t('extraction.need_two')}</p>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-stone-200 text-left text-xs text-stone-500 dark:border-stone-800">
              <th className="py-2 pr-3 font-medium">{t('extraction.field')}</th>
              {exts.map((e) => (
                <th key={e.id} className="py-2 pr-3 font-medium">
                  {who(e)}
                </th>
              ))}
              {detail.can_resolve && <th className="py-2 font-medium">{t('extraction.consensus')}</th>}
            </tr>
          </thead>
          <tbody>
            {cmp.data.fields.map((row) => {
              const f = byId[row.field_id]
              if (!f) return null
              return (
                <tr key={row.field_id} className={`border-b border-stone-100 align-top dark:border-stone-800 ${row.agree ? '' : 'bg-amber-50/60 dark:bg-amber-950/30'}`}>
                  <td className="py-2 pr-3 font-medium">{f.label}</td>
                  {exts.map((e) => (
                    <td key={e.id} className="py-2 pr-3">
                      {format(f, row.values[e.id])}
                      {detail.can_resolve && !row.agree && row.values[e.id] != null && (
                        <button
                          type="button"
                          className="ml-2 text-xs text-brand-600 dark:text-brand-300 hover:underline"
                          onClick={() => setCons({ ...current, [f.id]: row.values[e.id] })}
                        >
                          {t('extraction.use')}
                        </button>
                      )}
                    </td>
                  ))}
                  {detail.can_resolve && (
                    <td className="min-w-56 py-2">
                      <FieldInput
                        f={f}
                        value={current[f.id]}
                        onChange={(v) => setCons({ ...current, [f.id]: v })}
                      />
                    </td>
                  )}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {detail.can_resolve && (
        <div className="flex flex-wrap items-center gap-3">
          <Button disabled={saveConsensus.isPending} onClick={() => saveConsensus.mutate({ values: current, status: 'done' })}>
            {detail.consensus ? t('extraction.update_consensus') : t('extraction.save_consensus')}
          </Button>
          {detail.consensus && (
            <Button variant="danger" onClick={() => removeConsensus.mutate()}>
              {t('extraction.remove_consensus')}
            </Button>
          )}
          {saveConsensus.isSuccess && <span className="text-sm text-stone-500">{t('extraction.saved')}</span>}
          <ErrorText error={saveConsensus.error ?? removeConsensus.error} />
        </div>
      )}
    </Card>
  )
}

export default function ExtractionUnit() {
  const { t } = useTranslation()
  const { project } = useProjectContext()
  const { formId = '', recordId = '' } = useParams()
  const unit = useUnit(project.id, formId, recordId)
  const settings = useScreeningSettings(project.id)
  const [tab, setTab] = useState<'mine' | 'compare'>('mine')
  const [focus, setFocus] = useState<Focus | null>(null)
  const [report, setReport] = useState<string | null>(null)
  const d = unit.data
  if (unit.isLoading) return <p className="text-stone-500">{t('app.loading')}</p>
  if (!d) return <ErrorText error={unit.error} />

  const focusRecord = focus?.fileId ? d.files.find((f) => f.id === focus.fileId)?.record_id : undefined
  const rid = focusRecord ?? report ?? d.unit.record_id
  const s = settings.data
  const back = `/projetos/${project.id}/extracao?form=${formId}`

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Link to={back} className="text-sm text-brand-600 dark:text-brand-300 hover:underline">
          ← {t('extraction.back')}
        </Link>
        <span className="text-sm text-stone-500">
          {d.form.name} · {t(`extraction.state_${d.unit.state}`)}
        </span>
      </div>
      <div>
        <h1 className="text-xl font-semibold">{d.unit.label}</h1>
        <p className="text-stone-500">{d.unit.title}</p>
      </div>
      {d.can_see_others && (
        <div role="tablist" className="inline-flex rounded-md border border-stone-300 p-0.5 dark:border-stone-700">
          {(['mine', 'compare'] as const).map((k) => (
            <button
              key={k}
              type="button"
              role="tab"
              aria-selected={tab === k}
              onClick={() => setTab(k)}
              className={`rounded px-3 py-1 text-sm ${tab === k ? 'bg-brand-600 text-white' : 'hover:bg-stone-100 dark:hover:bg-stone-800'}`}
            >
              {t(`extraction.tab_${k}`)}
            </button>
          ))}
        </div>
      )}
      {tab === 'compare' && d.can_see_others ? (
        <Compare detail={d} />
      ) : (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <div className="space-y-2 lg:sticky lg:top-4 lg:self-start">
            {d.unit.report_ids.length > 1 && (
              <div className="flex flex-wrap gap-1 text-sm">
                {d.unit.report_ids.map((r, i) => (
                  <button
                    key={r}
                    type="button"
                    onClick={() => {
                      setReport(r)
                      setFocus(null)
                    }}
                    className={`rounded px-2 py-1 ${r === rid ? 'bg-stone-200 dark:bg-stone-700' : 'hover:bg-stone-100 dark:hover:bg-stone-800'}`}
                  >
                    {t('extraction.report_n', { n: i + 1 })}
                  </button>
                ))}
              </div>
            )}
            <FullTextPanel
              key={rid}
              pid={project.id}
              rid={rid}
              include={s?.highlight_include ?? []}
              exclude={s?.highlight_exclude ?? []}
              canUpload={project.my_role !== 'observer'}
              focus={focus}
              onClearFocus={() => setFocus(null)}
            />
          </div>
          <MyExtraction key={d.mine?.updated_at ?? 'new'} detail={d} onShow={setFocus} />
        </div>
      )}
    </div>
  )
}
