import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { useInstanceAI, useProjectAI, useProtocolAI } from '../../api/ai'
import { useJob } from '../../api/records'
import { useScreeningSettings, useSettingsActions } from '../../api/screening'
import type {
  CriteriaDraft,
  CriterionItem,
  ReasonGroups,
  ScreeningSettings,
  TagItem,
  TagProposals,
} from '../../api/types'
import { Button, Card, ErrorText, Input, Select } from '../../components/ui'
import { useProjectContext } from './context'

const itemLine = (it: CriterionItem) => {
  const base = it.definition ? `${it.name}: ${it.definition}` : it.name
  return it.examples.length ? `- ${base} (${it.examples.join('; ')})` : `- ${base}`
}
const itemsText = (items: CriterionItem[], kind: CriterionItem['kind']) =>
  items
    .filter((i) => i.kind === kind && i.name.trim())
    .map(itemLine)
    .join('\n')

const area =
  'w-full rounded-md border border-stone-300 bg-white px-3 py-2 text-sm dark:border-stone-700 dark:bg-stone-900 disabled:opacity-70'

/** A IA só roda com um modelo de triagem configurado na instalação e ligada no projeto. */
function useAIReady(pid: string) {
  const instance = useInstanceAI()
  const project = useProjectAI(pid)
  return {
    configured: !!instance.data?.screening.provider_id && !!instance.data?.screening.model,
    enabled: !!project.data?.enabled,
    loaded: !instance.isLoading && !project.isLoading,
  }
}

function AIHint({ ready }: { ready: ReturnType<typeof useAIReady> }) {
  const { t } = useTranslation()
  if (!ready.loaded || (ready.configured && ready.enabled)) return null
  return (
    <p className="text-sm text-amber-700 dark:text-amber-300">
      {ready.configured ? t('protocol_ai.not_enabled') : t('protocol_ai.not_configured')}{' '}
      <Link to={ready.configured ? '../ia' : '/ia'} className="underline">
        {t('protocol_ai.go_ai')}
      </Link>
    </p>
  )
}

/** Acompanha um job de IA e entrega o resultado uma única vez. */
function useJobOutcome<T>(pid: string, onDone: (result: T) => void) {
  const [jobId, setJobId] = useState<string | null>(null)
  const [applied, setApplied] = useState<string | null>(null)
  const job = useJob(pid, jobId)
  if (job.data?.status === 'done' && applied !== job.data.id) {
    setApplied(job.data.id)
    onDone(job.data.result as unknown as T)
  }
  const status = job.data?.status
  return {
    track: (id: string) => setJobId(id),
    running: !!jobId && (!status || status === 'queued' || status === 'running') && applied !== jobId,
    error: status === 'failed' ? job.data?.error || 'failed' : '',
  }
}

function SaveRow({
  onSave,
  pending,
  saved,
  error,
  label,
}: {
  onSave: () => void
  pending: boolean
  saved: boolean
  error: unknown
  label: string
}) {
  const { t } = useTranslation()
  return (
    <div className="flex flex-wrap items-center gap-3">
      <Button onClick={onSave} disabled={pending}>
        {label}
      </Button>
      {saved && (
        <span role="status" className="text-sm text-brand-700 dark:text-brand-100">
          {t('protocol.saved')}
        </span>
      )}
      <ErrorText error={error} />
    </div>
  )
}

export function CriteriaCard({ settings, canManage }: { settings: ScreeningSettings; canManage: boolean }) {
  const { t } = useTranslation()
  const { project } = useProjectContext()
  const ready = useAIReady(project.id)
  const { organize } = useProtocolAI(project.id)
  const { save } = useSettingsActions(project.id)
  const latest = useScreeningSettings(project.id).data ?? settings
  const [items, setItems] = useState<CriterionItem[]>(settings.criteria_items)
  const [summary, setSummary] = useState('')
  const [questions, setQuestions] = useState<string[]>([])
  const [answers, setAnswers] = useState('')
  const outcome = useJobOutcome<CriteriaDraft>(project.id, (r) => {
    setItems(r.items)
    setSummary(r.summary)
    setQuestions(r.questions)
    if (r.questions.length === 0) setAnswers('')
  })

  const hasText = !!(latest.inclusion_criteria.trim() || latest.exclusion_criteria.trim())
  const canRun = canManage && ready.configured && ready.enabled
  const busy = organize.isPending || outcome.running
  const run = (withAnswers: boolean) =>
    organize.mutate(
      {
        inclusion_criteria: latest.inclusion_criteria,
        exclusion_criteria: latest.exclusion_criteria,
        answers: withAnswers ? answers : '',
      },
      { onSuccess: (job) => outcome.track(job.id) },
    )
  const update = (i: number, patch: Partial<CriterionItem>) =>
    setItems(items.map((it, n) => (n === i ? { ...it, ...patch } : it)))
  const persist = (next: CriterionItem[]) =>
    save.mutate({ ...latest, criteria_items: next.filter((i) => i.name.trim()) })

  return (
    <Card className="space-y-4">
      <div>
        <h2 className="font-semibold">{t('protocol_ai.criteria_title')}</h2>
        <p className="text-sm text-stone-500">{t('protocol_ai.criteria_intro')}</p>
      </div>
      {canManage && <AIHint ready={ready} />}
      {canManage && (
        <div className="flex flex-wrap items-center gap-3">
          <Button onClick={() => run(false)} disabled={!canRun || busy}>
            {busy ? t('protocol_ai.organizing') : t('protocol_ai.organize')}
          </Button>
          <span className="text-xs text-stone-500">
            {hasText ? t('protocol_ai.uses_saved') : t('protocol_ai.draft_hint')}
          </span>
        </div>
      )}
      <ErrorText error={organize.error} />
      {outcome.error && (
        <p role="alert" className="text-sm text-red-700 dark:text-red-400">
          {t('protocol_ai.failed')} <span className="block text-xs opacity-80">{outcome.error}</span>
        </p>
      )}
      {summary && <p className="rounded-md bg-stone-50 p-3 text-sm dark:bg-stone-800">{summary}</p>}
      {questions.length > 0 && (
        <div className="space-y-2 rounded-md border border-amber-300 p-3 dark:border-amber-700">
          <p className="text-sm font-medium">{t('protocol_ai.questions')}</p>
          <ul className="list-inside list-disc text-sm">
            {questions.map((q) => (
              <li key={q}>{q}</li>
            ))}
          </ul>
          <textarea
            rows={3}
            className={area}
            aria-label={t('protocol_ai.answers')}
            placeholder={t('protocol_ai.answers_placeholder')}
            value={answers}
            onChange={(e) => setAnswers(e.target.value)}
          />
          <Button variant="ghost" onClick={() => run(true)} disabled={!canRun || busy || !answers.trim()}>
            {t('protocol_ai.reorganize')}
          </Button>
        </div>
      )}
      {items.length === 0 && <p className="text-sm text-stone-500">{t('protocol_ai.no_items')}</p>}
      <ul className="space-y-3">
        {items.map((it, i) => (
          <li key={i} className="space-y-2 rounded-md border border-stone-200 p-3 dark:border-stone-800">
            <div className="flex flex-wrap gap-2">
              <Select
                aria-label={t('protocol_ai.kind')}
                className="w-auto"
                value={it.kind}
                disabled={!canManage}
                onChange={(e) => update(i, { kind: e.target.value as CriterionItem['kind'] })}
              >
                <option value="include">{t('screening.inclusion')}</option>
                <option value="exclude">{t('screening.exclusion')}</option>
              </Select>
              <Input
                className="min-w-0 flex-1"
                aria-label={t('protocol_ai.name')}
                maxLength={150}
                value={it.name}
                disabled={!canManage}
                onChange={(e) => update(i, { name: e.target.value })}
              />
              {canManage && (
                <Button variant="danger" onClick={() => setItems(items.filter((_, n) => n !== i))}>
                  {t('protocol_ai.remove')}
                </Button>
              )}
            </div>
            <textarea
              rows={2}
              className={area}
              aria-label={t('protocol_ai.definition')}
              placeholder={t('protocol_ai.definition')}
              value={it.definition}
              disabled={!canManage}
              onChange={(e) => update(i, { definition: e.target.value })}
            />
            <textarea
              rows={2}
              className={area}
              aria-label={t('protocol_ai.examples')}
              placeholder={t('protocol_ai.examples')}
              value={it.examples.join('\n')}
              disabled={!canManage}
              onChange={(e) => update(i, { examples: e.target.value.split('\n') })}
            />
          </li>
        ))}
      </ul>
      {canManage && (
        <div className="space-y-3">
          <Button
            variant="ghost"
            onClick={() => setItems([...items, { kind: 'include', name: '', definition: '', examples: [] }])}
          >
            {t('protocol_ai.add_item')}
          </Button>
          <SaveRow
            label={t('protocol_ai.save_criteria')}
            onSave={() => persist(items)}
            pending={save.isPending}
            saved={save.isSuccess}
            error={save.error}
          />
          {items.some((i) => i.name.trim()) && (
            <div className="space-y-1">
              <Button
                variant="ghost"
                className="border border-stone-300 dark:border-stone-700"
                disabled={save.isPending}
                onClick={() => {
                  if (hasText && !window.confirm(t('protocol_ai.to_text_confirm'))) return
                  save.mutate({
                    ...latest,
                    criteria_items: items.filter((i) => i.name.trim()),
                    inclusion_criteria: itemsText(items, 'include'),
                    exclusion_criteria: itemsText(items, 'exclude'),
                  })
                }}
              >
                {t('protocol_ai.to_text')}
              </Button>
              <p className="text-xs text-stone-500">{t('protocol_ai.to_text_hint')}</p>
            </div>
          )}
          {latest.criteria_items.length > 0 && (
            <div className="space-y-1">
              <p className="text-xs text-stone-500">
                {t('protocol_ai.in_use', { count: latest.criteria_items.length })}
              </p>
              <Button
                variant="ghost"
                onClick={() => {
                  setItems([])
                  persist([])
                }}
              >
                {t('protocol_ai.back_to_text')}
              </Button>
            </div>
          )}
        </div>
      )}
    </Card>
  )
}

interface Proposal extends TagItem {
  fills: boolean
}

export function TagsCard({ settings, canManage }: { settings: ScreeningSettings; canManage: boolean }) {
  const { t } = useTranslation()
  const { project } = useProjectContext()
  const ready = useAIReady(project.id)
  const { suggestTags } = useProtocolAI(project.id)
  const { save } = useSettingsActions(project.id)
  const latest = useScreeningSettings(project.id).data ?? settings
  const [tags, setTags] = useState<TagItem[]>(settings.tag_vocabulary)
  const [proposals, setProposals] = useState<Proposal[]>([])
  const [picked, setPicked] = useState<Set<string>>(new Set())
  const [name, setName] = useState('')
  const outcome = useJobOutcome<TagProposals>(project.id, (r) => {
    const have = new Map(tags.map((tg) => [tg.name.toLowerCase(), tg]))
    const list: Proposal[] = []
    for (const p of r.tags) {
      const cur = have.get(p.name.toLowerCase())
      if (!cur) list.push({ ...p, fills: false })
      else if (!cur.description.trim() && p.description.trim()) list.push({ ...p, name: cur.name, fills: true })
    }
    setProposals(list)
    setPicked(new Set(list.map((p) => p.name.toLowerCase())))
  })
  const busy = suggestTags.isPending || outcome.running
  const canRun = canManage && ready.configured && ready.enabled

  const add = () => {
    const n = name.trim()
    if (!n || tags.some((tg) => tg.name.toLowerCase() === n.toLowerCase())) return
    setTags([...tags, { name: n.slice(0, 60), description: '' }])
    setName('')
  }
  const accept = () => {
    let next = [...tags]
    for (const p of proposals.filter((x) => picked.has(x.name.toLowerCase()))) {
      const idx = next.findIndex((tg) => tg.name.toLowerCase() === p.name.toLowerCase())
      if (idx >= 0) next[idx] = { ...next[idx], description: p.description }
      else next = [...next, { name: p.name, description: p.description }]
    }
    setTags(next)
    setProposals([])
  }

  return (
    <Card className="space-y-4">
      <div>
        <h2 className="font-semibold">{t('protocol_ai.tags_title')}</h2>
        <p className="text-sm text-stone-500">{t('protocol_ai.tags_intro')}</p>
      </div>
      {canManage && <AIHint ready={ready} />}
      {tags.length === 0 && <p className="text-sm text-stone-500">{t('protocol_ai.no_tags')}</p>}
      <ul className="space-y-2">
        {tags.map((tg, i) => (
          <li key={tg.name} className="flex flex-wrap gap-2">
            <span className="w-40 shrink-0 self-center text-sm font-medium">{tg.name}</span>
            <Input
              className="min-w-0 flex-1"
              aria-label={t('protocol_ai.tag_description', { name: tg.name })}
              placeholder={t('protocol_ai.tag_description_placeholder')}
              maxLength={300}
              value={tg.description}
              disabled={!canManage}
              onChange={(e) => setTags(tags.map((x, n) => (n === i ? { ...x, description: e.target.value } : x)))}
            />
            {canManage && (
              <Button variant="danger" onClick={() => setTags(tags.filter((_, n) => n !== i))}>
                {t('protocol_ai.remove')}
              </Button>
            )}
          </li>
        ))}
      </ul>
      {canManage && (
        <div className="flex gap-2">
          <Input
            value={name}
            maxLength={60}
            aria-label={t('protocol_ai.new_tag')}
            placeholder={t('protocol_ai.new_tag')}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault()
                add()
              }
            }}
          />
          <Button variant="ghost" onClick={add}>
            {t('protocol_ai.add_tag')}
          </Button>
        </div>
      )}
      {canManage && (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="ghost"
              className="border border-stone-300 dark:border-stone-700"
              disabled={!canRun || busy}
              onClick={() =>
                suggestTags.mutate(undefined, { onSuccess: (job) => outcome.track(job.id) })
              }
            >
              {busy ? t('protocol_ai.suggesting') : t('protocol_ai.suggest_tags')}
            </Button>
            <span className="text-xs text-stone-500">{t('protocol_ai.suggest_hint')}</span>
          </div>
          <ErrorText error={suggestTags.error} />
          {outcome.error && (
            <p role="alert" className="text-sm text-red-700 dark:text-red-400">
              {t('protocol_ai.failed')} <span className="block text-xs opacity-80">{outcome.error}</span>
            </p>
          )}
          {proposals.length > 0 && (
            <div className="space-y-2 rounded-md border border-brand-300 p-3 dark:border-brand-700">
              <p className="text-sm font-medium">{t('protocol_ai.proposals')}</p>
              <ul className="space-y-1">
                {proposals.map((p) => {
                  const key = p.name.toLowerCase()
                  return (
                    <li key={key}>
                      <label className="flex items-start gap-2 text-sm">
                        <input
                          type="checkbox"
                          className="mt-1 size-4 accent-brand-600"
                          checked={picked.has(key)}
                          onChange={(e) => {
                            const n = new Set(picked)
                            if (e.target.checked) n.add(key)
                            else n.delete(key)
                            setPicked(n)
                          }}
                        />
                        <span>
                          <span className="font-medium">{p.name}</span>
                          {p.fills && (
                            <span className="ml-2 text-xs text-stone-500">{t('protocol_ai.fills')}</span>
                          )}
                          <span className="block text-xs text-stone-500">{p.description}</span>
                        </span>
                      </label>
                    </li>
                  )
                })}
              </ul>
              <div className="flex gap-2">
                <Button onClick={accept} disabled={picked.size === 0}>
                  {t('protocol_ai.accept')}
                </Button>
                <Button variant="ghost" onClick={() => setProposals([])}>
                  {t('protocol_ai.dismiss')}
                </Button>
              </div>
            </div>
          )}
          <SaveRow
            label={t('protocol_ai.save_tags')}
            onSave={() =>
              save.mutate({ ...latest, tag_vocabulary: tags.filter((tg) => tg.name.trim()) })
            }
            pending={save.isPending}
            saved={save.isSuccess}
            error={save.error}
          />
        </div>
      )}
    </Card>
  )
}

interface GroupRow {
  label: string
  existing: boolean
  count: number
  members: string[]
  picked: boolean
}

/** Agrupa os motivos de exclusão que a IA propôs e transforma os grupos em motivos do protocolo. */
export function ReasonGroupsCard({ canManage }: { canManage: boolean }) {
  const { t } = useTranslation()
  const { project } = useProjectContext()
  const ready = useAIReady(project.id)
  const { organizeReasons, applyReasons } = useProtocolAI(project.id)
  const [rows, setRows] = useState<GroupRow[]>([])
  const outcome = useJobOutcome<ReasonGroups>(project.id, (r) =>
    setRows(r.groups.map((g) => ({ ...g, picked: true }))),
  )
  if (!canManage) return null
  const busy = organizeReasons.isPending || outcome.running
  const canRun = ready.configured && ready.enabled
  const nothing = outcome.error.includes('no_reasons_to_group')
  const patch = (i: number, p: Partial<GroupRow>) =>
    setRows(rows.map((r, n) => (n === i ? { ...r, ...p } : r)))
  return (
    <Card className="space-y-4">
      <div>
        <h2 className="font-semibold">{t('protocol_ai.reasons_title')}</h2>
        <p className="text-sm text-stone-500">{t('protocol_ai.reasons_intro')}</p>
      </div>
      <AIHint ready={ready} />
      <Button
        variant="ghost"
        className="border border-stone-300 dark:border-stone-700"
        disabled={!canRun || busy}
        onClick={() => organizeReasons.mutate(undefined, { onSuccess: (job) => outcome.track(job.id) })}
      >
        {busy ? t('protocol_ai.grouping') : t('protocol_ai.group_reasons')}
      </Button>
      <ErrorText error={organizeReasons.error} />
      {nothing && <p className="text-sm text-stone-500">{t('protocol_ai.reasons_none')}</p>}
      {outcome.error && !nothing && (
        <p role="alert" className="text-sm text-red-700 dark:text-red-400">
          {t('protocol_ai.failed')} <span className="block text-xs opacity-80">{outcome.error}</span>
        </p>
      )}
      {rows.length > 0 && (
        <div className="space-y-3">
          <ul className="space-y-2">
            {rows.map((r, i) => (
              <li key={i} className="space-y-1 rounded-md border border-stone-200 p-3 dark:border-stone-800">
                <div className="flex flex-wrap items-center gap-2">
                  <input
                    type="checkbox"
                    className="size-4 accent-brand-600"
                    aria-label={t('protocol_ai.reasons_pick', { label: r.label })}
                    checked={r.picked}
                    onChange={(e) => patch(i, { picked: e.target.checked })}
                  />
                  <Input
                    className="min-w-0 flex-1"
                    aria-label={t('protocol_ai.reasons_label')}
                    maxLength={200}
                    value={r.label}
                    onChange={(e) => patch(i, { label: e.target.value })}
                  />
                  <span className="text-xs text-stone-500">
                    {t('protocol_ai.reasons_count', { count: r.count })}
                  </span>
                  {r.existing && (
                    <span className="rounded-full bg-stone-100 px-2 text-xs dark:bg-stone-800">
                      {t('protocol_ai.reasons_existing')}
                    </span>
                  )}
                </div>
                <p className="text-xs text-stone-500">{r.members.join(' · ')}</p>
              </li>
            ))}
          </ul>
          <div className="flex flex-wrap items-center gap-3">
            <Button
              disabled={applyReasons.isPending || !rows.some((r) => r.picked && r.label.trim())}
              onClick={() =>
                applyReasons.mutate(
                  rows.filter((r) => r.picked && r.label.trim()).map((r) => ({ label: r.label, members: r.members })),
                  { onSuccess: () => setRows([]) },
                )
              }
            >
              {t('protocol_ai.reasons_apply')}
            </Button>
            <Button variant="ghost" onClick={() => setRows([])}>
              {t('protocol_ai.dismiss')}
            </Button>
          </div>
        </div>
      )}
      <ErrorText error={applyReasons.error} />
      {applyReasons.isSuccess && applyReasons.data && (
        <p role="status" className="text-sm text-brand-700 dark:text-brand-100">
          {t('protocol_ai.reasons_applied', applyReasons.data)}
        </p>
      )}
    </Card>
  )
}
