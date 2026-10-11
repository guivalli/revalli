import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { codingExportUrl, useCodes, useCodingActions, useExcerpts, useMatrix } from '../../api/synthesis'
import type { Code } from '../../api/types'
import { CodeDot } from '../../components/CodeDot'
import { Button, Card, ErrorText, Input, Select } from '../../components/ui'
import { CODE_COLORS, codeSubtree, flattenCodes } from '../../lib/codes'
import { useProjectContext } from './context'

function NewCode({ parent, onDone }: { parent: Code | null; onDone?: () => void }) {
  const { t } = useTranslation()
  const { project } = useProjectContext()
  const { createCode } = useCodingActions(project.id)
  const [name, setName] = useState('')
  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return
    const color = parent?.color || CODE_COLORS[Math.floor(Math.random() * CODE_COLORS.length)]
    createCode.mutate(
      { name, parent_id: parent?.id ?? null, color },
      {
        onSuccess: () => {
          setName('')
          onDone?.()
        },
      },
    )
  }
  return (
    <form onSubmit={submit} className="flex flex-wrap items-center gap-2">
      <Input
        aria-label={parent ? t('coding.subcode') : t('coding.new_code')}
        placeholder={parent ? t('coding.subcode') : t('coding.new_code')}
        className="max-w-xs"
        value={name}
        autoFocus={!!parent}
        onChange={(e) => setName(e.target.value)}
      />
      <Button type="submit" variant="ghost" className="border border-stone-300 dark:border-stone-700" disabled={createCode.isPending}>
        {t('coding.add')}
      </Button>
      {onDone && (
        <Button type="button" variant="ghost" onClick={onDone}>
          {t('coding.cancel')}
        </Button>
      )}
      <ErrorText error={createCode.error} />
    </form>
  )
}

function CodeRow({
  code,
  depth,
  codes,
  canEdit,
  canManage,
  onShow,
}: {
  code: Code
  depth: number
  codes: Code[]
  canEdit: boolean
  canManage: boolean
  onShow: (c: Code) => void
}) {
  const { t } = useTranslation()
  const { project } = useProjectContext()
  const { updateCode, deleteCode, mergeCode } = useCodingActions(project.id)
  const [mode, setMode] = useState<'view' | 'rename' | 'child' | 'merge'>('view')
  const [name, setName] = useState(code.name)
  const [color, setColor] = useState(code.color)
  const subtree = codeSubtree(codes, code.id)
  return (
    <li className="py-1.5" style={{ paddingLeft: depth * 20 }}>
      {mode === 'rename' ? (
        <form
          className="flex flex-wrap items-center gap-2"
          onSubmit={(e) => {
            e.preventDefault()
            updateCode.mutate({ id: code.id, body: { name, color } }, { onSuccess: () => setMode('view') })
          }}
        >
          <Input aria-label={t('coding.name')} className="max-w-xs" value={name} onChange={(e) => setName(e.target.value)} />
          <span className="flex gap-1">
            {CODE_COLORS.map((c) => (
              <button
                key={c}
                type="button"
                aria-label={c}
                aria-pressed={color === c}
                className={`size-5 rounded-full ${color === c ? 'ring-2 ring-stone-900 ring-offset-1 dark:ring-white' : ''}`}
                style={{ background: c }}
                onClick={() => setColor(c)}
              />
            ))}
          </span>
          <Button type="submit">{t('coding.save')}</Button>
          <Button type="button" variant="ghost" onClick={() => setMode('view')}>
            {t('coding.cancel')}
          </Button>
        </form>
      ) : (
        <div className="group flex flex-wrap items-center gap-2 text-sm">
          <CodeDot code={code} />
          <button type="button" className="font-medium hover:underline" onClick={() => onShow(code)}>
            {code.name}
          </button>
          <span className="text-xs text-stone-500">{t('coding.excerpts_count', { count: code.excerpts })}</span>
          {canEdit && (
            <span className="flex gap-1 opacity-70 group-hover:opacity-100">
              <button type="button" className="text-xs text-brand-600 hover:underline" onClick={() => setMode('child')}>
                + {t('coding.subcode')}
              </button>
              <button type="button" className="text-xs text-brand-600 hover:underline" onClick={() => setMode('rename')}>
                {t('coding.rename')}
              </button>
              {canManage && (
                <>
                  <button type="button" className="text-xs text-brand-600 hover:underline" onClick={() => setMode('merge')}>
                    {t('coding.merge')}
                  </button>
                  <button
                    type="button"
                    className="text-xs text-red-600 hover:underline"
                    onClick={() =>
                      window.confirm(t('coding.delete_confirm', { name: code.name })) && deleteCode.mutate(code.id)
                    }
                  >
                    {t('coding.delete')}
                  </button>
                </>
              )}
            </span>
          )}
        </div>
      )}
      {mode === 'child' && (
        <div className="mt-2" style={{ paddingLeft: 20 }}>
          <NewCode parent={code} onDone={() => setMode('view')} />
        </div>
      )}
      {mode === 'merge' && (
        <div className="mt-2 flex items-center gap-2" style={{ paddingLeft: 20 }}>
          <Select
            aria-label={t('coding.merge')}
            className="max-w-xs"
            defaultValue=""
            onChange={(e) => {
              const into = codes.find((c) => c.id === e.target.value)
              if (into && window.confirm(t('coding.merge_confirm', { from: code.name, into: into.name })))
                mergeCode.mutate({ id: code.id, into: into.id }, { onSuccess: () => setMode('view') })
            }}
          >
            <option value="">{t('coding.merge')}</option>
            {flattenCodes(codes)
              .filter((r) => !subtree.has(r.code.id))
              .map((r) => (
                <option key={r.code.id} value={r.code.id}>
                  {' '.repeat(r.depth * 3)}
                  {r.code.name}
                </option>
              ))}
          </Select>
          <Button variant="ghost" onClick={() => setMode('view')}>
            {t('coding.cancel')}
          </Button>
        </div>
      )}
      <ErrorText error={updateCode.error ?? deleteCode.error ?? mergeCode.error} />
    </li>
  )
}

function CodeExcerpts({ code, recordId, onClose }: { code: Code; recordId?: string; onClose: () => void }) {
  const { t } = useTranslation()
  const { project } = useProjectContext()
  const excerpts = useExcerpts(project.id, { codeId: code.id })
  const list = (excerpts.data ?? []).filter((e) => !recordId || e.record_id === recordId)
  return (
    <Card className="space-y-3">
      <div className="flex items-center gap-2">
        <CodeDot code={code} />
        <h2 className="mr-auto font-semibold">{t('coding.excerpts_of', { name: code.name })}</h2>
        <Button variant="ghost" onClick={onClose}>
          {t('coding.close')}
        </Button>
      </div>
      {list.length === 0 && !excerpts.isLoading && <p className="text-sm text-stone-500">{t('coding.no_excerpts')}</p>}
      <ul className="space-y-3">
        {list.map((e) => (
          <li key={e.id} className="border-l-4 pl-3 text-sm" style={{ borderColor: code.color || '#a8a29e' }}>
            <q className="italic">{e.text}</q>
            <p className="text-xs text-stone-500">
              <Link to={e.record_id} className="font-medium text-brand-600 hover:underline">
                {e.study}
              </Link>
              {e.page && ` · ${t('coding.page')} ${e.page}`} · {t('coding.by', { name: e.user_name })}
            </p>
            {e.note && <p className="text-xs text-stone-600 dark:text-stone-400">{e.note}</p>}
          </li>
        ))}
      </ul>
    </Card>
  )
}

function MatrixTable({ codes, onCell }: { codes: Code[]; onCell: (c: Code, recordId?: string) => void }) {
  const { t } = useTranslation()
  const { project } = useProjectContext()
  const matrix = useMatrix(project.id)
  const m = matrix.data
  if (!m || m.units.length === 0 || codes.length === 0) return null
  const rows = flattenCodes(codes)
  const count = (code: Code, rid: string) =>
    [...codeSubtree(codes, code.id)].reduce((a, id) => a + (m.cells[id]?.[rid] ?? 0), 0)
  return (
    <Card className="space-y-3">
      <div>
        <h2 className="font-semibold">{t('coding.matrix')}</h2>
        <p className="text-sm text-stone-500">{t('coding.matrix_hint')}</p>
      </div>
      <div className="overflow-x-auto">
        <table className="text-sm">
          <thead>
            <tr>
              <th />
              {m.units.map((u) => (
                <th key={u.record_id} title={u.title} className="px-2 pb-2 text-left text-xs font-medium whitespace-nowrap">
                  {u.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map(({ code, depth }) => (
              <tr key={code.id} className="border-t border-stone-100 dark:border-stone-800">
                <th scope="row" className="py-1 pr-4 text-left font-normal whitespace-nowrap" style={{ paddingLeft: depth * 16 }}>
                  <span className="inline-flex items-center gap-2">
                    <CodeDot code={code} />
                    {code.name}
                  </span>
                </th>
                {m.units.map((u) => {
                  const n = count(code, u.record_id)
                  return (
                    <td key={u.record_id} className="px-2 py-1 text-center">
                      {n > 0 ? (
                        <button
                          type="button"
                          aria-label={`${code.name} · ${u.label}: ${n}`}
                          className="min-w-7 rounded px-1.5 py-0.5 text-xs font-medium text-white"
                          style={{ background: code.color || '#78716c', opacity: Math.min(1, 0.45 + n * 0.15) }}
                          onClick={() => onCell(code, u.record_id)}
                        >
                          {n}
                        </button>
                      ) : (
                        <span className="text-stone-300 dark:text-stone-700">·</span>
                      )}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

export default function Coding() {
  const { t } = useTranslation()
  const { project, canManage } = useProjectContext()
  const codes = useCodes(project.id)
  const matrix = useMatrix(project.id)
  const [shown, setShown] = useState<{ code: Code; recordId?: string } | null>(null)
  const canEdit = canManage || ['reviewer', 'extractor'].includes(project.my_role ?? '')
  const list = codes.data ?? []
  const units = matrix.data?.units ?? []

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start gap-3">
        <div className="mr-auto">
          <h1 className="text-lg font-semibold">{t('coding.title')}</h1>
          <p className="text-sm text-stone-500">{t('coding.hint')}</p>
        </div>
        <a className="text-sm text-brand-600 hover:underline" href={codingExportUrl(project.id)}>
          {t('coding.export')}
        </a>
      </div>
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <Card className="space-y-3">
          <h2 className="font-semibold">{t('coding.codes')}</h2>
          {list.length === 0 && !codes.isLoading && <p className="text-sm text-stone-500">{t('coding.no_codes')}</p>}
          <ul>
            {flattenCodes(list).map(({ code, depth }) => (
              <CodeRow
                key={code.id}
                code={code}
                depth={depth}
                codes={list}
                canEdit={canEdit}
                canManage={canManage}
                onShow={(c) => setShown({ code: c })}
              />
            ))}
          </ul>
          {canEdit && <NewCode parent={null} />}
        </Card>
        <Card className="space-y-3">
          <h2 className="font-semibold">{t('coding.studies')}</h2>
          {units.length === 0 && !matrix.isLoading && <p className="text-sm text-stone-500">{t('coding.no_studies')}</p>}
          <ul className="divide-y divide-stone-200 dark:divide-stone-800">
            {units.map((u) => (
              <li key={u.record_id} className="flex flex-wrap items-center gap-3 py-2 text-sm">
                <div className="min-w-0 flex-1">
                  <p className="font-medium">{u.label}</p>
                  <p className="truncate text-stone-500">{u.title}</p>
                </div>
                {!u.has_pdf && <span className="text-xs text-stone-500">{t('coding.no_pdf')}</span>}
                <span className="text-xs text-stone-500">{t('coding.excerpts_count', { count: u.excerpts })}</span>
                <Link to={u.record_id} className="font-medium text-brand-600 hover:underline">
                  {t('coding.code_study')}
                </Link>
              </li>
            ))}
          </ul>
        </Card>
      </div>
      {shown && <CodeExcerpts code={shown.code} recordId={shown.recordId} onClose={() => setShown(null)} />}
      <MatrixTable codes={list} onCell={(code, recordId) => setShown({ code, recordId })} />
    </div>
  )
}
