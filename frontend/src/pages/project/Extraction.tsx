import { useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { exportUrl, useFormActions, useForms, useRob, useUnits } from '../../api/extraction'
import type { ExtractionFormT, UnitState } from '../../api/types'
import { SummaryPlot, TrafficLight } from '../../components/RobPlots'
import { Button, Card, ErrorText, Select } from '../../components/ui'
import { savePng, saveSvg } from '../../lib/download'
import { useProjectContext } from './context'

const TEMPLATES = ['study_characteristics', 'rob2', 'robins_i'] as const

const STATE_STYLE: Record<UnitState, string> = {
  pending: 'bg-stone-100 text-stone-600 dark:bg-stone-800 dark:text-stone-300',
  in_progress: 'bg-sky-50 text-sky-700 dark:bg-sky-950 dark:text-sky-300',
  complete: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300',
  conflict: 'bg-amber-50 text-amber-800 dark:bg-amber-950 dark:text-amber-300',
  agreed: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300',
  resolved: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300',
}

function NewForm({ onCreated }: { onCreated: (id: string) => void }) {
  const { t } = useTranslation()
  const { project } = useProjectContext()
  const { fromTemplate } = useFormActions(project.id)
  const [extractors, setExtractors] = useState(2)
  return (
    <Card className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold">{t('extraction.new_form')}</h2>
        <p className="text-sm text-stone-500">{t('extraction.new_form_hint')}</p>
      </div>
      <label className="flex items-center gap-2 text-sm">
        {t('extraction.extractors')}
        <Select className="w-20" value={extractors} onChange={(e) => setExtractors(Number(e.target.value))}>
          {[1, 2, 3].map((n) => (
            <option key={n}>{n}</option>
          ))}
        </Select>
      </label>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Link
          to="novo"
          className="rounded-md border border-dashed border-stone-300 p-4 text-sm hover:bg-stone-50 dark:border-stone-700 dark:hover:bg-stone-800"
        >
          <p className="font-medium">{t('extraction.blank')}</p>
          <p className="text-stone-500">{t('extraction.blank_hint')}</p>
        </Link>
        {TEMPLATES.map((tpl) => (
          <button
            key={tpl}
            type="button"
            disabled={fromTemplate.isPending}
            className="rounded-md border border-stone-300 p-4 text-left text-sm hover:bg-stone-50 disabled:opacity-50 dark:border-stone-700 dark:hover:bg-stone-800"
            onClick={() => fromTemplate.mutate({ template: tpl, extractors }, { onSuccess: (f) => onCreated(f.id) })}
          >
            <p className="font-medium">{t(`extraction.tpl_${tpl}`)}</p>
            <p className="text-stone-500">{t(`extraction.tpl_${tpl}_hint`)}</p>
          </button>
        ))}
      </div>
      <ErrorText error={fromTemplate.error} />
    </Card>
  )
}

function RobCharts({ form }: { form: ExtractionFormT }) {
  const { t } = useTranslation()
  const { project } = useProjectContext()
  const { data } = useRob(project.id, form.id, true)
  const light = useRef<SVGSVGElement>(null)
  const summary = useRef<SVGSVGElement>(null)
  if (!data) return null
  const name = form.name.toLowerCase().replace(/[^a-z0-9]+/g, '-')
  return (
    <Card className="space-y-4">
      <h2 className="text-lg font-semibold">{t('rob.charts')}</h2>
      {data.rows.length === 0 ? (
        <p className="text-sm text-stone-500">{t('rob.no_data')}</p>
      ) : (
        <>
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="mr-auto text-sm font-medium">{t('rob.traffic_light')}</h3>
              <Button variant="ghost" onClick={() => saveSvg(light.current, `${name}-semaforo`)}>
                SVG
              </Button>
              <Button variant="ghost" onClick={() => void savePng(light.current, `${name}-semaforo`)}>
                PNG
              </Button>
            </div>
            <div className="max-w-3xl overflow-x-auto rounded-md border border-stone-200 dark:border-stone-800">
              <TrafficLight ref={light} data={data} />
            </div>
          </div>
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="mr-auto text-sm font-medium">{t('rob.summary')}</h3>
              <Button variant="ghost" onClick={() => saveSvg(summary.current, `${name}-resumo`)}>
                SVG
              </Button>
              <Button variant="ghost" onClick={() => void savePng(summary.current, `${name}-resumo`)}>
                PNG
              </Button>
            </div>
            <div className="max-w-3xl overflow-x-auto rounded-md border border-stone-200 dark:border-stone-800">
              <SummaryPlot ref={summary} data={data} />
            </div>
          </div>
        </>
      )}
    </Card>
  )
}

function FormPanel({ form }: { form: ExtractionFormT }) {
  const { t } = useTranslation()
  const { project, canManage } = useProjectContext()
  const canResolve = canManage || project.my_role === 'arbitrator'
  const units = useUnits(project.id, form.id)
  const { runAI, remove } = useFormActions(project.id)
  const navigate = useNavigate()
  const list = units.data ?? []
  const hasAI = form.fields.some((f) => f.ai)
  const done = list.filter((u) => ['resolved', 'agreed', 'complete'].includes(u.state)).length

  return (
    <>
      <Card className="space-y-4">
        <div className="flex flex-wrap items-start gap-3">
          <div className="mr-auto">
            <h2 className="text-lg font-semibold">{form.name}</h2>
            <p className="text-sm text-stone-500">
              {t('extraction.form_meta', {
                version: form.version,
                count: form.extractors,
                fields: form.fields.filter((f) => f.type !== 'section').length,
              })}
            </p>
          </div>
          {canManage && (
            <Link to={`${form.id}/editar`} className="rounded-md px-3 py-2 text-sm font-medium text-stone-700 hover:bg-stone-200 dark:text-stone-300 dark:hover:bg-stone-800">
              {t('extraction.edit_form')}
            </Link>
          )}
          {canManage && hasAI && (
            <Button
              variant="ghost"
              className="border border-stone-300 dark:border-stone-700"
              disabled={runAI.isPending}
              onClick={() => runAI.mutate({ fid: form.id })}
            >
              {t('extraction.run_ai')}
            </Button>
          )}
          {canManage && (
            <Button
              variant="danger"
              onClick={() =>
                window.confirm(t('extraction.delete_confirm')) &&
                remove.mutate(form.id, { onSuccess: () => navigate('.', { replace: true }) })
              }
            >
              {t('extraction.delete_form')}
            </Button>
          )}
        </div>
        <ErrorText error={runAI.error ?? remove.error} />
        {runAI.isSuccess && <p className="text-sm text-stone-500">{t('extraction.ai_started')}</p>}
        {canResolve && (
          <p className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
            <a className="text-brand-600 dark:text-brand-300 hover:underline" href={exportUrl(project.id, form.id, 'wide')}>
              {t('extraction.export_wide')}
            </a>
            <a className="text-brand-600 dark:text-brand-300 hover:underline" href={exportUrl(project.id, form.id, 'long')}>
              {t('extraction.export_long')}
            </a>
          </p>
        )}
      </Card>

      <Card className="space-y-3">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-lg font-semibold">{t('extraction.studies')}</h2>
          {list.length > 0 && (
            <span className="text-sm text-stone-500">{t('extraction.progress', { done, total: list.length })}</span>
          )}
        </div>
        {units.isLoading ? (
          <p className="text-sm text-stone-500">{t('app.loading')}</p>
        ) : list.length === 0 ? (
          <p className="text-sm text-stone-500">{t('extraction.no_studies')}</p>
        ) : (
          <ul className="divide-y divide-stone-200 dark:divide-stone-800">
            {list.map((u) => (
              <li key={u.record_id} className="flex flex-wrap items-center gap-3 py-2 text-sm">
                <div className="min-w-0 flex-1">
                  <p className="font-medium">{u.label}</p>
                  <p className="truncate text-stone-500">
                    {u.title}
                    {u.report_ids.length > 1 && ` · ${t('studies.reports', { count: u.report_ids.length })}`}
                  </p>
                </div>
                {u.has_ai && <span className="text-xs text-stone-500">{t('extraction.has_ai')}</span>}
                <span className={`rounded px-2 py-0.5 text-xs ${STATE_STYLE[u.state]}`}>
                  {t(`extraction.state_${u.state}`)}
                </span>
                <span className="w-28 text-xs text-stone-500">
                  {u.mine ? t(`extraction.mine_${u.mine}`) : t('extraction.mine_none')}
                </span>
                <Link to={`${form.id}/${u.record_id}`} className="font-medium text-brand-600 dark:text-brand-300 hover:underline">
                  {u.mine === 'done' || u.state === 'resolved' ? t('extraction.open') : t('extraction.extract')}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Card>
      {form.kind === 'rob' && canResolve && <RobCharts form={form} />}
    </>
  )
}

export default function Extraction() {
  const { t } = useTranslation()
  const { project, canManage } = useProjectContext()
  const forms = useForms(project.id)
  const [params, setParams] = useSearchParams()
  const list = forms.data ?? []
  const wanted = params.get('form')
  const adding = params.get('novo') === '1'
  const current = adding ? undefined : (list.find((f) => f.id === wanted) ?? list[0])

  if (forms.isLoading) return <p className="text-stone-500">{t('app.loading')}</p>

  return (
    <div className="space-y-6">
      {list.length > 0 && (
        <div className="flex flex-wrap items-center gap-2" role="tablist">
          {list.map((f) => (
            <button
              key={f.id}
              type="button"
              role="tab"
              aria-selected={f.id === current?.id}
              onClick={() => setParams({ form: f.id })}
              className={`rounded-md px-3 py-1.5 text-sm ${
                f.id === current?.id
                  ? 'bg-brand-600 text-white'
                  : 'border border-stone-300 hover:bg-stone-100 dark:border-stone-700 dark:hover:bg-stone-800'
              }`}
            >
              {f.name}
            </button>
          ))}
          {canManage && (
            <button
              type="button"
              aria-selected={adding}
              role="tab"
              onClick={() => setParams({ novo: '1' })}
              className={`rounded-md px-3 py-1.5 text-sm ${adding ? 'bg-brand-600 text-white' : 'text-brand-600 dark:text-brand-300 hover:underline'}`}
            >
              {t('extraction.new_form')}
            </button>
          )}
        </div>
      )}
      {(adding || list.length === 0) &&
        (canManage ? (
          <NewForm onCreated={(id) => setParams({ form: id })} />
        ) : (
          <Card>
            <p className="text-sm text-stone-500">{t('extraction.no_forms')}</p>
          </Card>
        ))}
      {current && <FormPanel key={current.id} form={current} />}
    </div>
  )
}
