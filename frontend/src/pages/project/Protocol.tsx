import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useReasons, useScreeningSettings, useSettingsActions } from '../../api/screening'
import type { ScreeningSettings } from '../../api/types'
import { Button, Card, ErrorText, Field, Input } from '../../components/ui'
import { useProjectContext } from './context'
import { CriteriaCard, ReasonGroupsCard, TagsCard } from './ProtocolAI'

const area =
  'w-full rounded-md border border-stone-300 bg-white px-3 py-2 text-sm dark:border-stone-700 dark:bg-stone-900 disabled:opacity-70'

const toLines = (v: string[]) => v.join('\n')
const fromLines = (v: string) => v.split(/\n|;/).map((s) => s.trim()).filter(Boolean)

function SettingsForm({ initial, canManage }: { initial: ScreeningSettings; canManage: boolean }) {
  const { t } = useTranslation()
  const { project } = useProjectContext()
  const { save } = useSettingsActions(project.id)
  // Os critérios detalhados e as etiquetas são salvos pelos cartões abaixo; aqui só se
  // sobrescrevem os campos deste formulário, partindo do que está salvo agora.
  const latest = useScreeningSettings(project.id).data
  const [s, setS] = useState(initial)
  const [inc, setInc] = useState(toLines(initial.highlight_include))
  const [exc, setExc] = useState(toLines(initial.highlight_exclude))
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate(
      { ...(latest ?? s), ...s, highlight_include: fromLines(inc), highlight_exclude: fromLines(exc),
        criteria_items: (latest ?? s).criteria_items, tag_vocabulary: (latest ?? s).tag_vocabulary },
      {
        // Mostra os termos como o servidor guardou (limpos e sem repetição)
        onSuccess: (saved) => {
          setS(saved)
          setInc(toLines(saved.highlight_include))
          setExc(toLines(saved.highlight_exclude))
        },
      },
    )
  }
  return (
    <Card>
      <form onSubmit={submit} className="space-y-5">
        <h2 className="font-semibold">{t('protocol.title')}</h2>
        {!canManage && <p className="text-sm text-stone-500">{t('protocol.readonly')}</p>}
        <fieldset disabled={!canManage} className="space-y-5">
          <label className="flex items-start gap-3">
            <input
              type="checkbox"
              className="mt-1 size-4 accent-brand-600"
              checked={s.blind}
              onChange={(e) => setS({ ...s, blind: e.target.checked })}
            />
            <span>
              <span className="block text-sm font-medium">{t('protocol.blind')}</span>
              <span className="block text-xs text-stone-500">{t('protocol.blind_hint')}</span>
            </span>
          </label>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('protocol.reviewers_ta')}>
              <Input
                type="number"
                min={1}
                max={5}
                value={s.reviewers_title_abstract}
                onChange={(e) => setS({ ...s, reviewers_title_abstract: Number(e.target.value) })}
              />
            </Field>
            <Field label={t('protocol.reviewers_ft')}>
              <Input
                type="number"
                min={1}
                max={5}
                value={s.reviewers_full_text}
                onChange={(e) => setS({ ...s, reviewers_full_text: Number(e.target.value) })}
              />
            </Field>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('protocol.inclusion')}>
              <textarea
                rows={5}
                className={area}
                value={s.inclusion_criteria}
                onChange={(e) => setS({ ...s, inclusion_criteria: e.target.value })}
              />
            </Field>
            <Field label={t('protocol.exclusion')}>
              <textarea
                rows={5}
                className={area}
                value={s.exclusion_criteria}
                onChange={(e) => setS({ ...s, exclusion_criteria: e.target.value })}
              />
            </Field>
            <Field label={t('protocol.hl_include')} hint={t('protocol.hl_hint')}>
              <textarea rows={5} className={area} value={inc} onChange={(e) => setInc(e.target.value)} />
            </Field>
            <Field label={t('protocol.hl_exclude')}>
              <textarea rows={5} className={area} value={exc} onChange={(e) => setExc(e.target.value)} />
            </Field>
          </div>
        </fieldset>
        <ErrorText error={save.error} />
        {save.isSuccess && (
          <p role="status" className="text-sm text-brand-700 dark:text-brand-100">
            {t('protocol.saved')}
          </p>
        )}
        {canManage && (
          <Button type="submit" disabled={save.isPending}>
            {t('protocol.save')}
          </Button>
        )}
      </form>
    </Card>
  )
}

function ReasonsCard({ canManage }: { canManage: boolean }) {
  const { t } = useTranslation()
  const { project } = useProjectContext()
  const { data } = useReasons(project.id)
  const { addReason, updateReason } = useSettingsActions(project.id)
  const [label, setLabel] = useState('')
  const [editing, setEditing] = useState<{ id: string; label: string } | null>(null)
  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (!label.trim()) return
    addReason.mutate(label, { onSuccess: () => setLabel('') })
  }
  return (
    <Card className="space-y-3">
      <h2 className="font-semibold">{t('protocol.reasons')}</h2>
      <ol className="space-y-1">
        {data?.map((r, i) => (
          <li key={r.id} className="flex items-center justify-between gap-2 text-sm">
            {editing?.id === r.id ? (
              <form
                className="flex flex-1 gap-2"
                onSubmit={(e) => {
                  e.preventDefault()
                  if (!editing.label.trim()) return
                  updateReason.mutate(
                    { id: r.id, label: editing.label.trim() },
                    { onSuccess: () => setEditing(null) },
                  )
                }}
              >
                <Input
                  autoFocus
                  aria-label={t('protocol.edit_reason')}
                  maxLength={200}
                  value={editing.label}
                  onChange={(e) => setEditing({ id: r.id, label: e.target.value })}
                />
                <Button type="submit" disabled={updateReason.isPending}>
                  {t('protocol.save_reason')}
                </Button>
                <Button type="button" variant="ghost" onClick={() => setEditing(null)}>
                  {t('projects.cancel')}
                </Button>
              </form>
            ) : (
              <>
                <span className={r.archived ? 'text-stone-400 line-through' : ''}>
                  <span className="mr-2 inline-block w-5 text-right tabular-nums text-stone-500">{i + 1}.</span>
                  {r.label}
                </span>
                {canManage && (
                  <span className="flex shrink-0">
                    <Button variant="ghost" onClick={() => setEditing({ id: r.id, label: r.label })}>
                      {t('protocol.edit_reason')}
                    </Button>
                    <Button
                      variant="ghost"
                      onClick={() => updateReason.mutate({ id: r.id, archived: !r.archived })}
                    >
                      {r.archived ? t('protocol.unarchive') : t('protocol.archive')}
                    </Button>
                  </span>
                )}
              </>
            )}
          </li>
        ))}
      </ol>
      {canManage && (
        <form onSubmit={submit} className="flex gap-2">
          <Input
            placeholder={t('protocol.new_reason')}
            aria-label={t('protocol.new_reason')}
            value={label}
            maxLength={200}
            onChange={(e) => setLabel(e.target.value)}
          />
          <Button type="submit" disabled={addReason.isPending}>
            {t('protocol.add_reason')}
          </Button>
        </form>
      )}
      <ErrorText error={addReason.error ?? updateReason.error} />
    </Card>
  )
}

export default function Protocol() {
  const { project, canManage } = useProjectContext()
  const { data } = useScreeningSettings(project.id)
  return (
    <div className="space-y-6">
      {data && (
        <SettingsForm
          key={`${data.inclusion_criteria}\u0000${data.exclusion_criteria}`}
          initial={data}
          canManage={canManage}
        />
      )}
      {data && <CriteriaCard settings={data} canManage={canManage} />}
      {data && <TagsCard settings={data} canManage={canManage} />}
      <ReasonsCard canManage={canManage} />
      <ReasonGroupsCard canManage={canManage} />
    </div>
  )
}
