import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useForm, useFormActions } from '../../api/extraction'
import type { ColumnDef, ExtractionFormT, FieldDef, FieldType } from '../../api/types'
import { Button, Card, ErrorText, Field, Input, Select } from '../../components/ui'
import { slugify } from '../../lib/fields'
import { useProjectContext } from './context'

const BASE_TYPES: FieldType[] = ['section', 'text', 'long_text', 'number', 'integer', 'choice', 'multi', 'boolean', 'table']
const ROB_TYPES: FieldType[] = ['signal', 'judgement']

const blankField = (id: string): FieldDef => ({
  id,
  label: '',
  type: 'text',
  help: '',
  required: false,
  options: [],
  columns: [],
  rows: [],
  ai: false,
  ai_hint: '',
  domain: '',
  algorithm: '',
  show_if: [],
})

const lines = (s: string) =>
  s
    .split('\n')
    .map((x) => x.trim())
    .filter(Boolean)

function ColumnsEditor({ cols, onChange }: { cols: ColumnDef[]; onChange: (c: ColumnDef[]) => void }) {
  const { t } = useTranslation()
  return (
    <div className="space-y-2">
      <p className="text-sm font-medium">{t('builder.columns')}</p>
      {cols.map((c, i) => (
        <div key={i} className="flex items-center gap-2">
          <Input
            aria-label={t('builder.column_label')}
            value={c.label}
            onChange={(e) => {
              const label = e.target.value
              const taken = new Set(cols.filter((_, j) => j !== i).map((x) => x.id))
              onChange(cols.map((x, j) => (j === i ? { ...x, label, id: slugify(label || 'coluna', taken, 'col') } : x)))
            }}
          />
          <Select
            aria-label={t('builder.type')}
            className="w-36"
            value={c.type}
            onChange={(e) => onChange(cols.map((x, j) => (j === i ? { ...x, type: e.target.value as ColumnDef['type'] } : x)))}
          >
            {(['text', 'number', 'integer'] as const).map((ty) => (
              <option key={ty} value={ty}>
                {t(`builder.type_${ty}`)}
              </option>
            ))}
          </Select>
          <button type="button" className="px-1 text-stone-400 hover:text-red-600" aria-label={t('builder.remove')} onClick={() => onChange(cols.filter((_, j) => j !== i))}>
            ×
          </button>
        </div>
      ))}
      <button
        type="button"
        className="text-sm text-brand-600 dark:text-brand-300 hover:underline"
        onClick={() => onChange([...cols, { id: slugify('coluna', new Set(cols.map((c) => c.id)), 'col'), label: '', type: 'text' }])}
      >
        {t('builder.add_column')}
      </button>
    </div>
  )
}

function FieldEditor({
  f,
  index,
  total,
  kind,
  locked,
  taken,
  onChange,
  onMove,
  onRemove,
}: {
  f: FieldDef
  index: number
  total: number
  kind: ExtractionFormT['kind']
  locked: boolean
  taken: Set<string>
  onChange: (f: FieldDef) => void
  onMove: (dir: -1 | 1) => void
  onRemove: () => void
}) {
  const { t } = useTranslation()
  const types = kind === 'rob' ? [...BASE_TYPES, ...ROB_TYPES] : BASE_TYPES
  const hasOptions = ['choice', 'multi', 'judgement', 'signal'].includes(f.type)
  const section = f.type === 'section'
  return (
    <li
      className={`space-y-3 rounded-md border p-3 ${
        section ? 'border-brand-200 bg-brand-50/40 dark:border-stone-700 dark:bg-stone-800/40' : 'border-stone-200 dark:border-stone-800'
      }`}
    >
      <div className="flex flex-wrap items-end gap-2">
        <div className="min-w-48 flex-1">
          <Field label={section ? t('builder.section_title') : t('builder.label')}>
            <Input
              value={f.label}
              onChange={(e) => {
                const label = e.target.value
                onChange({ ...f, label, id: locked ? f.id : slugify(label || 'campo', taken) })
              }}
            />
          </Field>
        </div>
        <div className="w-44">
          <Field label={t('builder.type')}>
            <Select
              value={f.type}
              disabled={locked && (f.type === 'signal' || f.type === 'judgement')}
              onChange={(e) => {
                const type = e.target.value as FieldType
                onChange({
                  ...f,
                  type,
                  options: type === 'signal' ? ['Y', 'PY', 'PN', 'N', 'NI'] : f.options,
                  columns: type === 'table' && !f.columns.length ? [{ id: 'grupo', label: 'Grupo', type: 'text' }] : f.columns,
                })
              }}
            >
              {types.map((ty) => (
                <option key={ty} value={ty}>
                  {t(`builder.type_${ty}`)}
                </option>
              ))}
            </Select>
          </Field>
        </div>
        <div className="flex gap-1">
          <Button variant="ghost" aria-label={t('builder.up')} disabled={index === 0} onClick={() => onMove(-1)}>
            ↑
          </Button>
          <Button variant="ghost" aria-label={t('builder.down')} disabled={index === total - 1} onClick={() => onMove(1)}>
            ↓
          </Button>
          <Button variant="danger" aria-label={t('builder.remove')} onClick={onRemove}>
            ×
          </Button>
        </div>
      </div>
      {!section && (
        <>
          <p className="text-xs text-stone-500">
            {t('builder.column_id', { id: f.id })}
            {f.show_if.length > 0 && ` · ${t('builder.conditional')}`}
            {f.algorithm && ` · ${t('builder.computed')}`}
          </p>
          <Field label={t('builder.help')}>
            <Input value={f.help} onChange={(e) => onChange({ ...f, help: e.target.value })} />
          </Field>
          {hasOptions && f.type !== 'signal' && (
            <Field label={t('builder.options')} hint={t('builder.options_hint')}>
              <textarea
                rows={Math.min(8, Math.max(3, f.options.length + 1))}
                disabled={f.type === 'judgement' && locked}
                className="w-full rounded-md border border-stone-300 bg-white px-3 py-2 text-sm dark:border-stone-700 dark:bg-stone-900"
                value={f.options.join('\n')}
                onChange={(e) => onChange({ ...f, options: e.target.value.split('\n') })}
                onBlur={(e) => onChange({ ...f, options: lines(e.target.value) })}
              />
            </Field>
          )}
          {f.type === 'table' && (
            <>
              <ColumnsEditor cols={f.columns} onChange={(columns) => onChange({ ...f, columns })} />
              <Field label={t('builder.rows')} hint={t('builder.rows_hint')}>
                <textarea
                  rows={2}
                  className="w-full rounded-md border border-stone-300 bg-white px-3 py-2 text-sm dark:border-stone-700 dark:bg-stone-900"
                  value={f.rows.join('\n')}
                  onChange={(e) => onChange({ ...f, rows: e.target.value.split('\n') })}
                  onBlur={(e) => onChange({ ...f, rows: lines(e.target.value) })}
                />
              </Field>
            </>
          )}
          <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={f.required} onChange={(e) => onChange({ ...f, required: e.target.checked })} />
              {t('builder.required')}
            </label>
            {f.type !== 'judgement' && (
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={f.ai} onChange={(e) => onChange({ ...f, ai: e.target.checked })} />
                {t('builder.ai')}
              </label>
            )}
          </div>
          {f.ai && (
            <Field label={t('builder.ai_hint')}>
              <Input value={f.ai_hint} onChange={(e) => onChange({ ...f, ai_hint: e.target.value })} />
            </Field>
          )}
        </>
      )}
    </li>
  )
}

function Builder({ initial }: { initial?: ExtractionFormT }) {
  const { t } = useTranslation()
  const { project } = useProjectContext()
  const navigate = useNavigate()
  const { create, update } = useFormActions(project.id)
  const [name, setName] = useState(initial?.name ?? '')
  const [extractors, setExtractors] = useState(initial?.extractors ?? 2)
  const [fields, setFields] = useState<FieldDef[]>(initial?.fields ?? [])
  const [locked] = useState(() => new Set(initial?.fields.map((f) => f.id) ?? []))
  const kind = initial?.kind ?? 'extraction'
  const save = initial ? update : create

  const setAt = (i: number, f: FieldDef) => setFields((all) => all.map((x, j) => (j === i ? f : x)))
  const move = (i: number, dir: -1 | 1) =>
    setFields((all) => {
      const next = [...all]
      ;[next[i], next[i + dir]] = [next[i + dir], next[i]]
      return next
    })
  const add = (type: FieldType) =>
    setFields((all) => {
      const id = slugify(type === 'section' ? 'secao' : 'campo', new Set(all.map((f) => f.id)))
      return [...all, { ...blankField(id), type }]
    })
  const submit = () => {
    const body = {
      name,
      kind,
      extractors,
      fields: fields.map((f) => ({ ...f, options: lines(f.options.join('\n')), rows: lines(f.rows.join('\n')) })),
    }
    const done = (f: ExtractionFormT) => navigate(`/projetos/${project.id}/extracao?form=${f.id}`)
    if (initial) update.mutate({ fid: initial.id, body }, { onSuccess: done })
    else create.mutate(body, { onSuccess: done })
  }

  return (
    <div className="space-y-6">
      <Link
        to={`/projetos/${project.id}/extracao${initial ? `?form=${initial.id}` : ''}`}
        className="text-sm text-brand-600 dark:text-brand-300 hover:underline"
      >
        ← {t('extraction.back')}
      </Link>
      <Card className="space-y-4">
        <h2 className="text-lg font-semibold">{initial ? t('builder.edit_title') : t('builder.new_title')}</h2>
        {initial && <p className="text-sm text-stone-500">{t('builder.versions_hint', { version: initial.version })}</p>}
        <div className="grid gap-3 sm:grid-cols-[1fr_12rem]">
          <Field label={t('builder.name')}>
            <Input value={name} onChange={(e) => setName(e.target.value)} />
          </Field>
          <Field label={t('extraction.extractors')}>
            <Select value={extractors} onChange={(e) => setExtractors(Number(e.target.value))}>
              {[1, 2, 3].map((n) => (
                <option key={n}>{n}</option>
              ))}
            </Select>
          </Field>
        </div>
      </Card>
      <Card className="space-y-3">
        <h2 className="text-lg font-semibold">{t('builder.fields')}</h2>
        {fields.length === 0 && <p className="text-sm text-stone-500">{t('builder.no_fields')}</p>}
        <ul className="space-y-3">
          {fields.map((f, i) => (
            <FieldEditor
              key={i}
              f={f}
              index={i}
              total={fields.length}
              kind={kind}
              locked={locked.has(f.id)}
              taken={new Set(fields.filter((_, j) => j !== i).map((x) => x.id))}
              onChange={(nf) => setAt(i, nf)}
              onMove={(dir) => move(i, dir)}
              onRemove={() =>
                (!locked.has(f.id) || window.confirm(t('builder.remove_confirm'))) &&
                setFields((all) => all.filter((_, j) => j !== i))
              }
            />
          ))}
        </ul>
        <div className="flex flex-wrap gap-2">
          <Button variant="ghost" className="border border-stone-300 dark:border-stone-700" onClick={() => add('text')}>
            {t('builder.add_field')}
          </Button>
          <Button variant="ghost" className="border border-stone-300 dark:border-stone-700" onClick={() => add('section')}>
            {t('builder.add_section')}
          </Button>
        </div>
      </Card>
      <div className="flex items-center gap-3">
        <Button disabled={!name.trim() || save.isPending} onClick={submit}>
          {t('builder.save')}
        </Button>
        <ErrorText error={save.error} />
      </div>
    </div>
  )
}

export default function FormBuilder() {
  const { t } = useTranslation()
  const { project } = useProjectContext()
  const { formId } = useParams()
  const form = useForm(project.id, formId)
  if (formId && form.isLoading) return <p className="text-stone-500">{t('app.loading')}</p>
  return <Builder key={form.data?.id ?? 'new'} initial={formId ? form.data : undefined} />
}
