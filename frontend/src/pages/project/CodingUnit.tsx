import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'
import { useMe } from '../../api/hooks'
import { useScreeningSettings } from '../../api/screening'
import { useCodes, useCodingActions, useCodingUnits, useExcerpts } from '../../api/synthesis'
import type { Code, Excerpt } from '../../api/types'
import { CodeDot } from '../../components/CodeDot'
import { FullTextPanel } from '../../components/FullTextPanel'
import { Button, Card, ErrorText, Input } from '../../components/ui'
import { flattenCodes } from '../../lib/codes'
import { useProjectContext } from './context'

type Focus = { page: number; text: string; fileId: string | null }

const textarea =
  'w-full rounded-md border border-stone-300 bg-white px-3 py-2 text-sm dark:border-stone-700 dark:bg-stone-900'

function CodePicker({
  codes,
  chosen,
  onToggle,
}: {
  codes: Code[]
  chosen: Set<string>
  onToggle: (id: string) => void
}) {
  return (
    <div className="max-h-72 space-y-0.5 overflow-auto rounded-md border border-stone-200 p-2 dark:border-stone-800">
      {flattenCodes(codes).map(({ code, depth }) => (
        <label
          key={code.id}
          className="flex cursor-pointer items-center gap-2 rounded px-1 py-0.5 text-sm hover:bg-stone-100 dark:hover:bg-stone-800"
          style={{ paddingLeft: 4 + depth * 18 }}
        >
          <input
            type="checkbox"
            className="accent-brand-600"
            checked={chosen.has(code.id)}
            onChange={() => onToggle(code.id)}
          />
          <CodeDot code={code} />
          {code.name}
        </label>
      ))}
    </div>
  )
}

function ExcerptItem({
  e,
  codes,
  canEdit,
  onShow,
}: {
  e: Excerpt
  codes: Code[]
  canEdit: boolean
  onShow: (f: Focus) => void
}) {
  const { t } = useTranslation()
  const { project } = useProjectContext()
  const { updateExcerpt, deleteExcerpt } = useCodingActions(project.id)
  const [editing, setEditing] = useState(false)
  const [chosen, setChosen] = useState(() => new Set(e.code_ids))
  const byId = new Map(codes.map((c) => [c.id, c]))
  return (
    <li className="space-y-1.5 border-t border-stone-100 pt-3 first:border-0 first:pt-0 dark:border-stone-800">
      <q className="block text-sm italic">{e.text}</q>
      <div className="flex flex-wrap gap-1">
        {e.code_ids.map((id) => {
          const c = byId.get(id)
          return c ? (
            <span key={id} className="inline-flex items-center gap-1 rounded-full bg-stone-100 px-2 py-0.5 text-xs dark:bg-stone-800">
              <CodeDot code={c} />
              {c.name}
            </span>
          ) : null
        })}
      </div>
      {e.note && <p className="text-xs text-stone-600 dark:text-stone-400">{e.note}</p>}
      <p className="flex flex-wrap gap-x-3 text-xs text-stone-500">
        {e.page && <span>{t('coding.page')} {e.page}</span>}
        <span>{t('coding.by', { name: e.user_name })}</span>
        {e.page && (
          <button
            type="button"
            className="text-brand-600 dark:text-brand-300 hover:underline"
            onClick={() => onShow({ page: e.page!, text: e.text, fileId: e.file_id })}
          >
            {t('coding.show_in_pdf')}
          </button>
        )}
        {canEdit && (
          <>
            <button type="button" className="text-brand-600 dark:text-brand-300 hover:underline" onClick={() => setEditing(!editing)}>
              {t('coding.edit_codes')}
            </button>
            <button
              type="button"
              className="text-red-600 hover:underline"
              onClick={() => deleteExcerpt.mutate(e.id)}
            >
              {t('coding.delete')}
            </button>
          </>
        )}
      </p>
      {editing && (
        <div className="space-y-2">
          <CodePicker
            codes={codes}
            chosen={chosen}
            onToggle={(id) => {
              const next = new Set(chosen)
              if (next.has(id)) next.delete(id)
              else next.add(id)
              setChosen(next)
            }}
          />
          <Button
            disabled={chosen.size === 0 || updateExcerpt.isPending}
            onClick={() =>
              updateExcerpt.mutate({ id: e.id, body: { code_ids: [...chosen] } }, { onSuccess: () => setEditing(false) })
            }
          >
            {t('coding.save')}
          </Button>
        </div>
      )}
      <ErrorText error={updateExcerpt.error ?? deleteExcerpt.error} />
    </li>
  )
}

export default function CodingUnit() {
  const { t } = useTranslation()
  const { project, canManage } = useProjectContext()
  const { recordId = '' } = useParams()
  const units = useCodingUnits(project.id)
  const { data: me } = useMe()
  const codes = useCodes(project.id)
  const excerpts = useExcerpts(project.id, { recordId })
  const settings = useScreeningSettings(project.id)
  const { createExcerpt } = useCodingActions(project.id)
  const [focus, setFocus] = useState<Focus | null>(null)
  const [report, setReport] = useState<string | null>(null)
  const [selection, setSelection] = useState<{ text: string; page: number | null; fileId: string | null }>({
    text: '',
    page: null,
    fileId: null,
  })
  const [chosen, setChosen] = useState<Set<string>>(new Set())
  const [note, setNote] = useState('')
  const unit = units.data?.find((u) => u.record_id === recordId)
  const canEdit = canManage || ['reviewer', 'extractor'].includes(project.my_role ?? '')
  const codeList = codes.data ?? []
  const list = excerpts.data ?? []

  if (units.isLoading) return <p className="text-stone-500">{t('app.loading')}</p>
  if (!unit) return <p className="text-stone-500">{t('errors.study_not_found')}</p>

  const focusRecord = focus?.fileId ? list.find((e) => e.file_id === focus.fileId)?.file_record_id : null
  const rid = focusRecord ?? report ?? unit.record_id
  const apply = () =>
    createExcerpt.mutate(
      {
        record_id: unit.record_id,
        text: selection.text,
        file_id: selection.fileId,
        page: selection.page,
        note,
        code_ids: [...chosen],
      },
      {
        onSuccess: () => {
          setSelection({ text: '', page: null, fileId: null })
          setNote('')
          window.getSelection()?.removeAllRanges()
        },
      },
    )

  return (
    <div className="space-y-4">
      <Link to=".." relative="path" className="text-sm text-brand-600 dark:text-brand-300 hover:underline">
        ← {t('coding.back')}
      </Link>
      <div>
        <h1 className="text-xl font-semibold">{unit.label}</h1>
        <p className="text-stone-500">{unit.title}</p>
      </div>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,26rem)]">
        <div className="space-y-2 lg:sticky lg:top-4 lg:self-start">
          {unit.report_ids.length > 1 && (
            <div className="flex flex-wrap gap-1 text-sm">
              {unit.report_ids.map((r, i) => (
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
            include={settings.data?.highlight_include ?? []}
            exclude={settings.data?.highlight_exclude ?? []}
            canUpload={canEdit}
            focus={focus}
            onClearFocus={() => setFocus(null)}
            onSelect={
              canEdit ? (sel) => setSelection({ text: sel.text, page: sel.page, fileId: sel.fileId }) : undefined
            }
          />
        </div>
        <div className="space-y-4">
          {canEdit && (
            <Card className="space-y-3">
              <div>
                <h2 className="font-semibold">{t('coding.selection')}</h2>
                <p className="text-xs text-stone-500">{t('coding.selection_hint')}</p>
              </div>
              <textarea
                rows={4}
                aria-label={t('coding.manual')}
                placeholder={t('coding.manual')}
                className={textarea}
                value={selection.text}
                onChange={(e) => setSelection({ ...selection, text: e.target.value })}
              />
              <label className="flex items-center gap-2 text-sm">
                {t('coding.page')}
                <Input
                  type="number"
                  min={1}
                  className="w-24"
                  value={selection.page ?? ''}
                  onChange={(e) => setSelection({ ...selection, page: e.target.value ? Number(e.target.value) : null })}
                />
              </label>
              <p className="text-sm font-medium">{t('coding.pick_codes')}</p>
              {codeList.length ? (
                <CodePicker
                  codes={codeList}
                  chosen={chosen}
                  onToggle={(id) => {
                    const next = new Set(chosen)
                    if (next.has(id)) next.delete(id)
                    else next.add(id)
                    setChosen(next)
                  }}
                />
              ) : (
                <p className="text-sm text-stone-500">{t('coding.no_codes')}</p>
              )}
              <Input aria-label={t('coding.note')} placeholder={t('coding.note')} value={note} onChange={(e) => setNote(e.target.value)} />
              <ErrorText error={createExcerpt.error} />
              <Button disabled={!selection.text.trim() || chosen.size === 0 || createExcerpt.isPending} onClick={apply}>
                {t('coding.apply')}
              </Button>
            </Card>
          )}
          <Card className="space-y-3">
            <h2 className="font-semibold">{t('coding.study_excerpts')}</h2>
            {list.length === 0 && !excerpts.isLoading && <p className="text-sm text-stone-500">{t('coding.no_excerpts')}</p>}
            <ul className="space-y-3">
              {list.map((e) => (
                <ExcerptItem
                  key={e.id + e.code_ids.join()}
                  e={e}
                  codes={codeList}
                  canEdit={canManage || (canEdit && e.user_id === me?.id)}
                  onShow={setFocus}
                />
              ))}
            </ul>
          </Card>
        </div>
      </div>
    </div>
  )
}
