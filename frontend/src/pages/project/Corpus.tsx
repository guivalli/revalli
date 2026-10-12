import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import {
  indexIncomplete,
  useCorpusActions,
  useCorpusMessages,
  useCorpusStatus,
} from '../../api/corpus'
import { useMe } from '../../api/hooks'
import { useRecentJobs } from '../../api/records'
import type { CorpusMessage, CorpusSource } from '../../api/types'
import { FullTextPanel } from '../../components/FullTextPanel'
import { Button, Card, ErrorText, Field, Select } from '../../components/ui'
import { useProjectContext } from './context'

const area =
  'w-full rounded-md border border-stone-300 bg-white px-3 py-2 text-sm dark:border-stone-700 dark:bg-stone-900 disabled:opacity-70'

type Open = { source: CorpusSource } | null

/** A resposta com os marcadores [n] viram botões; os de citação não conferida ficam em âmbar. */
function AnswerText({
  message,
  onOpen,
}: {
  message: CorpusMessage
  onOpen: (s: CorpusSource) => void
}) {
  const bySource = new Map(message.sources.map((s) => [s.n, s]))
  return (
    <p className="whitespace-pre-wrap text-sm leading-relaxed">
      {message.answer.split(/(\[\d+\])/g).map((part, i) => {
        const m = /^\[(\d+)\]$/.exec(part)
        const src = m ? bySource.get(Number(m[1])) : undefined
        if (!src) return part
        return (
          <button
            key={i}
            type="button"
            onClick={() => onOpen(src)}
            className={
              src.verified
                ? 'mx-0.5 rounded px-1 text-xs font-semibold text-emerald-700 hover:bg-emerald-100 dark:text-emerald-300 dark:hover:bg-emerald-950'
                : 'mx-0.5 rounded px-1 text-xs font-semibold text-amber-700 underline decoration-dotted hover:bg-amber-100 dark:text-amber-300 dark:hover:bg-amber-950'
            }
          >
            [{src.n}]
          </button>
        )
      })}
    </p>
  )
}

function Message({
  message,
  onOpen,
  onRemove,
}: {
  message: CorpusMessage
  onOpen: (s: CorpusSource) => void
  onRemove: () => void
}) {
  const { t } = useTranslation()
  return (
    <Card className="space-y-3">
      <div className="flex items-start justify-between gap-3">
        <p className="font-medium">{message.question}</p>
        <Button variant="danger" onClick={onRemove}>
          {t('corpus.remove')}
        </Button>
      </div>
      {message.answer ? (
        <>
          <AnswerText message={message} onOpen={onOpen} />
          {message.unsupported_numbers.length > 0 && (
            <p role="alert" className="text-sm text-amber-700 dark:text-amber-300">
              {t('corpus.numbers', { list: message.unsupported_numbers.join(', ') })}
            </p>
          )}
          {message.answerable && !message.grounded && (
            <p role="alert" className="text-sm text-amber-700 dark:text-amber-300">
              {t('corpus.not_grounded')}
            </p>
          )}
        </>
      ) : (
        <p className="text-sm text-stone-500">{t('corpus.no_hits')}</p>
      )}
      {message.sources.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-medium uppercase tracking-wide text-stone-500">
            {t('corpus.sources')}
          </p>
          <ol className="space-y-2">
            {message.sources.map((s) => (
              <li key={s.n} className="rounded-md bg-stone-50 p-3 text-sm dark:bg-stone-900">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <span>
                    <span className="font-semibold">[{s.n}]</span> {s.title}
                    <span className="text-stone-500">
                      {' '}
                      · {[s.authors[0], s.year].filter(Boolean).join(' · ')} ·{' '}
                      {t('corpus.page', { page: s.page })}
                    </span>
                  </span>
                  <button
                    type="button"
                    className="text-brand-600 dark:text-brand-300 hover:underline"
                    onClick={() => onOpen(s)}
                  >
                    {t('corpus.open_pdf')}
                  </button>
                </div>
                {s.quote && (
                  <blockquote className="mt-1 border-l-2 border-stone-300 pl-3 text-stone-600 dark:border-stone-700 dark:text-stone-400">
                    {s.quote}
                  </blockquote>
                )}
                <p
                  className={
                    s.verified
                      ? 'mt-1 text-xs text-emerald-700 dark:text-emerald-300'
                      : 'mt-1 text-xs text-amber-700 dark:text-amber-300'
                  }
                >
                  {s.verified ? '✓ ' + t('corpus.verified') : '⚠ ' + t('corpus.unverified')}
                </p>
              </li>
            ))}
          </ol>
        </div>
      )}
      <p className="text-xs text-stone-500">{t('corpus.model', { model: message.model })}</p>
    </Card>
  )
}

export default function Corpus() {
  const { t } = useTranslation()
  const { project, canManage } = useProjectContext()
  const [waiting, setWaiting] = useState(false)
  const status = useCorpusStatus(project.id, waiting)
  const messages = useCorpusMessages(project.id)
  const { data: me } = useMe()
  const recent = useRecentJobs(project.id, waiting)
  const { index, ask, remove } = useCorpusActions(project.id)
  const [question, setQuestion] = useState('')
  const [scope, setScope] = useState<'included' | 'all'>('included')
  const [followUp, setFollowUp] = useState(false)
  const [open, setOpen] = useState<Open>(null)

  const s = status.data
  const busy = index.isPending || (waiting && (!s || indexIncomplete(s)))
  const history = messages.data ?? []
  // Os trechos são indexados mesmo quando os embeddings falham; a tela avisa o motivo
  const lastIndex = (recent.data ?? []).find((j) => j.kind === 'corpus_index')
  const embedProblem =
    lastIndex?.status === 'done' && typeof lastIndex.result.embeddings_error === 'string'
      ? lastIndex.result.embeddings_error
      : null
  const ready = !!s && s.enabled && s.chunks > 0 && !!s.chat_model

  const submit = () =>
    ask.mutate(
      { question: question.trim(), scope, follow_up: followUp && history.length > 0 },
      {
        onSuccess: () => {
          setQuestion('')
          setFollowUp(false)
        },
      },
    )

  return (
    <div className="space-y-6">
      <Card className="space-y-3">
        <div>
          <h2 className="font-semibold">{t('corpus.title')}</h2>
          <p className="text-sm text-stone-500">{t('corpus.hint')}</p>
        </div>
        {s && !s.enabled && (
          <p className="text-sm text-amber-700 dark:text-amber-300">
            {t('corpus.not_enabled')}{' '}
            <Link to="../ia" className="underline">
              {t('tabs.ai')}
            </Link>
          </p>
        )}
        {s && s.enabled && !s.chat_model && (
          <p className="text-sm text-amber-700 dark:text-amber-300">{t('corpus.no_model')}</p>
        )}
        {s && (
          <ul className="space-y-1 text-sm text-stone-600 dark:text-stone-400">
            <li>{t('corpus.indexed', { chunks: s.chunks })}</li>
            {s.pending_files > 0 && <li>{t('corpus.pending', { count: s.pending_files })}</li>}
            <li>
              {s.embeddings_model
                ? t('corpus.embedded', {
                    n: s.embedded,
                    chunks: s.chunks,
                    model: s.embeddings_model,
                  })
                : t('corpus.text_only')}
            </li>
          </ul>
        )}
        {s && s.chunks === 0 && s.pending_files === 0 && (
          <p className="text-sm text-stone-500">{t('corpus.empty')}</p>
        )}
        {embedProblem && (
          <p role="alert" className="text-sm text-amber-700 dark:text-amber-300">
            {embedProblem === 'embeddings_unsupported'
              ? t('corpus.embeddings_unsupported', { model: String(lastIndex?.result.embeddings ?? '') })
              : t('corpus.embeddings_failed', { error: embedProblem })}{' '}
            {me?.is_admin && (
              <Link to="/ia" className="underline">
                {t('corpus.open_ai_settings')}
              </Link>
            )}
          </p>
        )}
        {canManage && s && s.enabled && (
          <div>
            <Button
              variant="ghost"
              className="border border-stone-300 dark:border-stone-700"
              disabled={busy || !indexIncomplete(s)}
              onClick={() => {
                setWaiting(true)
                index.mutate(undefined, { onError: () => setWaiting(false) })
              }}
            >
              {busy ? t('corpus.indexing') : t('corpus.index')}
            </Button>
          </div>
        )}
        <ErrorText error={index.error} />
      </Card>

      <Card className="space-y-4">
        <Field label={t('corpus.question')}>
          <textarea
            rows={3}
            className={area}
            value={question}
            placeholder={t('corpus.placeholder')}
            disabled={!ready}
            onChange={(e) => setQuestion(e.target.value)}
          />
        </Field>
        <div className="flex flex-wrap items-end gap-4">
          <Field label={t('corpus.scope')}>
            <Select
              value={scope}
              onChange={(e) => setScope(e.target.value as 'included' | 'all')}
              disabled={!ready}
            >
              <option value="included">{t('corpus.scope_included')}</option>
              <option value="all">{t('corpus.scope_all')}</option>
            </Select>
          </Field>
          {history.length > 0 && (
            <label className="flex items-center gap-2 pb-2 text-sm">
              <input
                type="checkbox"
                className="size-4 accent-brand-600"
                checked={followUp}
                onChange={(e) => setFollowUp(e.target.checked)}
              />
              {t('corpus.follow_up')}
            </label>
          )}
          <Button disabled={!ready || question.trim().length < 3 || ask.isPending} onClick={submit}>
            {ask.isPending ? t('corpus.asking') : t('corpus.ask')}
          </Button>
        </div>
        <ErrorText error={ask.error ?? remove.error} />
      </Card>

      {open && (
        <div className="space-y-2">
          <Button variant="ghost" onClick={() => setOpen(null)}>
            {t('corpus.close_pdf')}
          </Button>
          <FullTextPanel
            key={open.source.record_id}
            pid={project.id}
            rid={open.source.record_id}
            include={[]}
            exclude={[]}
            canUpload={false}
            focus={{
              page: open.source.page,
              text: open.source.quote || open.source.excerpt.slice(0, 200),
              fileId: open.source.file_id,
            }}
          />
        </div>
      )}

      <div className="space-y-3">
        <h3 className="text-sm font-semibold">{t('corpus.history')}</h3>
        {history.length === 0 && <p className="text-sm text-stone-500">{t('corpus.no_history')}</p>}
        {[...history].reverse().map((m) => (
          <Message
            key={m.id}
            message={m}
            onOpen={(src) => setOpen({ source: src })}
            onRemove={() => remove.mutate(m.id)}
          />
        ))}
      </div>
    </div>
  )
}
