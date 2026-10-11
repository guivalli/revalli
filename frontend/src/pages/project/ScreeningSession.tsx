import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router-dom'
import {
  useLabels,
  useQueue,
  useReasons,
  useScreeningActions,
  useScreeningSettings,
} from '../../api/screening'
import type { DecisionKind, Phase, ScreeningItem } from '../../api/types'
import { FullTextPanel } from '../../components/FullTextPanel'
import { HighlightedText } from '../../components/HighlightedText'
import { RecordLinks } from '../../components/RecordView'
import { Button, Card, ErrorText, Input } from '../../components/ui'
import { useProjectContext } from './context'

const isTyping = (el: EventTarget | null) =>
  el instanceof HTMLElement && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.isContentEditable)

function LabelsInput({
  value,
  onChange,
  suggestions,
}: {
  value: string[]
  onChange: (v: string[]) => void
  suggestions: string[]
}) {
  const { t } = useTranslation()
  const [text, setText] = useState('')
  const add = () => {
    const v = text.trim()
    if (v && !value.some((x) => x.toLowerCase() === v.toLowerCase())) onChange([...value, v])
    setText('')
  }
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-1">
        {value.map((l) => (
          <button
            key={l}
            type="button"
            onClick={() => onChange(value.filter((x) => x !== l))}
            className="rounded-full bg-brand-50 px-2 py-0.5 text-xs text-brand-700 hover:line-through dark:bg-stone-800 dark:text-brand-100"
          >
            {l} ×
          </button>
        ))}
      </div>
      <Input
        list="revalli-labels"
        aria-label={t('screening.labels')}
        placeholder={t('screening.labels_placeholder')}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            e.preventDefault()
            add()
          }
        }}
        onBlur={add}
      />
      <datalist id="revalli-labels">
        {suggestions.map((s) => (
          <option key={s} value={s} />
        ))}
      </datalist>
    </div>
  )
}

export default function ScreeningSession() {
  const { t } = useTranslation()
  const { project } = useProjectContext()
  const [params] = useSearchParams()
  const phase = (params.get('fase') === 'full_text' ? 'full_text' : 'title_abstract') as Phase
  const settings = useScreeningSettings(project.id)
  const reasons = useReasons(project.id)
  const labelsQuery = useLabels(project.id)
  const queue = useQueue(project.id, phase)
  const { decide } = useScreeningActions(project.id, phase)

  // Fila local: o que já decidi nesta sessão sai da lista; dá para voltar pelo histórico
  const [done, setDone] = useState<Set<string>>(new Set())
  const [skipped, setSkipped] = useState<string[]>([])
  const [history, setHistory] = useState<ScreeningItem[]>([])
  const [viewing, setViewing] = useState<ScreeningItem | null>(null)
  const [excluding, setExcluding] = useState(false)
  const [reasonIds, setReasonIds] = useState<string[]>([])
  const [labels, setLabels] = useState<string[]>([])
  const [note, setNote] = useState('')
  const topRef = useRef<HTMLDivElement>(null)

  const pending = useMemo(() => {
    const items = (queue.data?.items ?? []).filter((i) => !done.has(i.id))
    // Pulados vão para o fim
    return [...items.filter((i) => !skipped.includes(i.id)), ...items.filter((i) => skipped.includes(i.id))]
  }, [queue.data, done, skipped])

  const current = viewing ?? pending[0] ?? null
  const activeReasons = (reasons.data ?? []).filter((r) => !r.archived)

  // Ao trocar de registro, carrega o que eu já tinha marcado nele (ajuste durante o render)
  const formKey = current ? `${current.id}:${current.my_decision?.created_at ?? ''}` : ''
  const [loadedKey, setLoadedKey] = useState(formKey)
  if (loadedKey !== formKey) {
    setLoadedKey(formKey)
    setExcluding(false)
    setReasonIds(current?.my_decision?.reason_ids ?? [])
    setLabels(current?.my_decision?.labels ?? [])
    setNote(current?.my_decision?.note ?? '')
  }
  useEffect(() => {
    topRef.current?.scrollIntoView({ block: 'start' })
  }, [current?.id])

  // Quando a fila local acaba e o servidor tem mais, busca o próximo lote
  const fetched = queue.data?.items.length ?? 0
  const more = (queue.data?.remaining ?? 0) > fetched
  const { refetch, isFetching } = queue
  useEffect(() => {
    if (!viewing && pending.length === 0 && more && !isFetching) void refetch()
  }, [pending.length, viewing, more, isFetching, refetch])

  const submit = useCallback(
    (decision: DecisionKind | null, target: ScreeningItem | null = current) => {
      if (!target) return
      const item = target
      decide.mutate(
        {
          record_id: item.id,
          decision,
          reason_ids: decision === 'exclude' ? reasonIds : [],
          labels,
          note,
        },
        {
          onSuccess: (res) => {
            const updated = { ...item, my_decision: res ?? null }
            setHistory((h) => [...h.filter((x) => x.id !== item.id), updated])
            if (decision === null) {
              setDone((d) => {
                const n = new Set(d)
                n.delete(item.id)
                return n
              })
              setViewing(null)
            } else {
              setDone((d) => new Set(d).add(item.id))
              setViewing(null)
            }
          },
        },
      )
    },
    [current, decide, reasonIds, labels, note],
  )

  const goBack = useCallback(() => {
    if (!history.length) return
    const idx = viewing ? history.findIndex((h) => h.id === viewing.id) : history.length
    if (idx > 0) setViewing(history[idx - 1])
  }, [history, viewing])

  const skip = useCallback(() => {
    if (viewing) {
      const idx = history.findIndex((h) => h.id === viewing.id)
      setViewing(idx >= 0 && idx < history.length - 1 ? history[idx + 1] : null)
    } else if (current) {
      setSkipped((s) => [...s.filter((x) => x !== current.id), current.id])
    }
  }, [viewing, history, current])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setExcluding(false)
        ;(document.activeElement as HTMLElement | null)?.blur()
        return
      }
      if (isTyping(e.target) || e.ctrlKey || e.metaKey || e.altKey || decide.isPending) return
      const k = e.key.toLowerCase()
      if (excluding) {
        const n = Number(e.key)
        if (n >= 1 && n <= activeReasons.length) {
          const id = activeReasons[n - 1].id
          setReasonIds((r) => (r.includes(id) ? r.filter((x) => x !== id) : [...r, id]))
          e.preventDefault()
        } else if (e.key === 'Enter') {
          submit('exclude')
          e.preventDefault()
        }
        return
      }
      if (k === 'i') submit('include')
      else if (k === 'm') submit('maybe')
      else if (k === 'e') {
        if (activeReasons.length) setExcluding(true)
        else submit('exclude')
      } else if (k === 'u') {
        // Desfaz a decisão do registro aberto ou, se ele não tem, a última desta sessão
        const target = current?.my_decision ? current : history.findLast((h) => h.my_decision)
        if (target) submit(null, target)
      }
      else if (e.key === 'ArrowLeft') goBack()
      else if (e.key === 'ArrowRight') skip()
      else return
      e.preventDefault()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [excluding, activeReasons, submit, goBack, skip, current, history, decide.isPending])

  const s = settings.data
  const hlInc = s?.highlight_include ?? []
  const hlExc = s?.highlight_exclude ?? []
  const back = (
    <Link to={`../triagem?fase=${phase}`} className="text-sm text-brand-600 hover:underline">
      ← {t('screening.back')}
    </Link>
  )

  if (queue.isLoading) return <p className="text-stone-500">{t('app.loading')}</p>
  if (queue.error) return <ErrorText error={queue.error} />
  if (!current)
    return (
      <div className="space-y-4">
        {back}
        <Card className="space-y-2 text-center">
          <p className="font-medium">{t('screening.done_title')}</p>
          <p className="text-sm text-stone-500">{t('screening.done_body')}</p>
          {history.length > 0 && (
            <Button variant="ghost" onClick={goBack}>
              ← {t('screening.previous')}
            </Button>
          )}
        </Card>
      </div>
    )

  const doneInBatch = (queue.data?.items ?? []).filter((i) => done.has(i.id)).length
  const remaining = Math.max(0, (queue.data?.remaining ?? 0) - doneInBatch)
  const my = current.my_decision

  return (
    <div ref={topRef} className="space-y-4 scroll-mt-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        {back}
        <span className="text-sm text-stone-500">
          {t(`screening.phase_${phase}`)} · {t('screening.counter', { remaining })}
        </span>
      </div>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <Card className="space-y-4">
          <h2 className="text-xl font-semibold leading-snug">
            <HighlightedText text={current.title || t('records.no_title')} include={hlInc} exclude={hlExc} />
          </h2>
          <p className="text-sm text-stone-500">
            {[current.authors.slice(0, 6).join('; ') + (current.authors.length > 6 ? ' et al.' : ''), current.year, current.journal]
              .filter(Boolean)
              .join(' · ')}
          </p>
          {current.publication_type && (
            <p className="text-xs text-stone-500">{current.publication_type}</p>
          )}
          <div className="whitespace-pre-line text-[15px] leading-relaxed">
            {current.abstract ? (
              <HighlightedText text={current.abstract} include={hlInc} exclude={hlExc} />
            ) : (
              <span className="text-stone-500">{t('records.no_abstract')}</span>
            )}
          </div>
          {current.keywords.length > 0 && (
            <p className="text-xs text-stone-500">
              {t('records.keywords')}:{' '}
              <HighlightedText text={current.keywords.join('; ')} include={hlInc} exclude={hlExc} />
            </p>
          )}
          <RecordLinks r={current} />
        </Card>
        {phase === 'full_text' && (
          <div className="lg:col-start-1">
            <FullTextPanel
              key={current.id}
              pid={project.id}
              rid={current.id}
              include={hlInc}
              exclude={hlExc}
              canUpload={project.my_role !== 'observer'}
            />
          </div>
        )}

        <div className="space-y-4 lg:col-start-2 lg:row-span-2 lg:row-start-1">
          <Card className="space-y-3 p-4">
            {my && (
              <p className="text-sm text-stone-500">
                {t('screening.your_decision', { decision: t(`decision.${my.decision === 'maybe' ? 'maybe_done' : my.decision === 'include' ? 'included' : 'excluded'}`) })}
              </p>
            )}
            <div className="grid grid-cols-3 gap-2">
              <Button
                className="bg-green-700 hover:bg-green-800"
                disabled={decide.isPending}
                onClick={() => submit('include')}
              >
                {t('decision.include')} <kbd className="ml-1 opacity-70">I</kbd>
              </Button>
              <Button
                className="bg-amber-600 hover:bg-amber-700"
                disabled={decide.isPending}
                onClick={() => submit('maybe')}
              >
                {t('decision.maybe')} <kbd className="ml-1 opacity-70">M</kbd>
              </Button>
              <Button
                className="bg-red-700 hover:bg-red-800"
                disabled={decide.isPending}
                onClick={() => (activeReasons.length ? setExcluding(true) : submit('exclude'))}
              >
                {t('decision.exclude')} <kbd className="ml-1 opacity-70">E</kbd>
              </Button>
            </div>
            {excluding && (
              <div className="space-y-2 rounded-md border border-red-200 p-3 dark:border-red-900">
                <p className="text-sm font-medium">{t('screening.reasons')}</p>
                <ul className="space-y-1">
                  {activeReasons.map((r, i) => (
                    <li key={r.id}>
                      <label className="flex items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          className="accent-red-700"
                          checked={reasonIds.includes(r.id)}
                          onChange={() =>
                            setReasonIds((x) => (x.includes(r.id) ? x.filter((y) => y !== r.id) : [...x, r.id]))
                          }
                        />
                        <kbd className="w-4 text-xs text-stone-500">{i + 1}</kbd>
                        {r.label}
                      </label>
                    </li>
                  ))}
                </ul>
                <p className="text-xs text-stone-500">{t('screening.reasons_hint')}</p>
                <Button className="w-full bg-red-700 hover:bg-red-800" onClick={() => submit('exclude')}>
                  {t('screening.confirm_exclude')}
                </Button>
              </div>
            )}
            <ErrorText error={decide.error} />
            <div className="flex justify-between">
              <Button variant="ghost" disabled={!history.length} onClick={goBack}>
                ← {t('screening.previous')}
              </Button>
              {my && (
                <Button variant="ghost" onClick={() => submit(null)}>
                  {t('decision.undo')}
                </Button>
              )}
              <Button variant="ghost" onClick={skip}>
                {t('screening.skip')} →
              </Button>
            </div>
          </Card>
          <Card className="space-y-3 p-4">
            <div>
              <p className="mb-1 text-sm font-medium">{t('screening.labels')}</p>
              <LabelsInput value={labels} onChange={setLabels} suggestions={labelsQuery.data ?? []} />
            </div>
            <label className="block">
              <span className="mb-1 block text-sm font-medium">{t('screening.note')}</span>
              <textarea
                rows={3}
                className="w-full rounded-md border border-stone-300 bg-white px-3 py-2 text-sm dark:border-stone-700 dark:bg-stone-900"
                value={note}
                onChange={(e) => setNote(e.target.value)}
              />
            </label>
          </Card>
          {(s?.inclusion_criteria || s?.exclusion_criteria) && (
            <Card className="space-y-2 p-4 text-sm">
              <p className="font-medium">{t('screening.criteria')}</p>
              {s.inclusion_criteria && (
                <div>
                  <p className="text-xs text-green-700 dark:text-green-400">{t('screening.inclusion')}</p>
                  <p className="whitespace-pre-line">{s.inclusion_criteria}</p>
                </div>
              )}
              {s.exclusion_criteria && (
                <div>
                  <p className="text-xs text-red-700 dark:text-red-400">{t('screening.exclusion')}</p>
                  <p className="whitespace-pre-line">{s.exclusion_criteria}</p>
                </div>
              )}
            </Card>
          )}
          <p className="text-xs text-stone-500">{t('screening.shortcuts')}</p>
        </div>
      </div>
    </div>
  )
}
