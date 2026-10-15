import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useRecentJobs } from '../../api/records'
import {
  useAssistChat,
  useDatabases,
  useSnowballInfo,
  useSourceActions,
  useSourceFields,
} from '../../api/sources'
import type { ApiSource, AssistTurn, Job, SearchRow } from '../../api/types'
import { SearchBuilder } from '../../components/SearchBuilder'
import { emptyRow } from '../../components/searchRows'
import { Button, Card, ErrorText, Field, Input, Select } from '../../components/ui'
import { useProjectContext } from './context'

/** As bases do projeto (escolhidas no cartão Bases do projeto) e as que têm busca direta. */
function useProjectBases() {
  const { project } = useProjectContext()
  const databases = useDatabases(project.id)
  const enabled = databases.data?.enabled ?? []
  const directIds = new Set((databases.data?.catalog ?? []).filter((d) => d.direct).map((d) => d.id))
  const direct = enabled.filter((id) => directIds.has(id)) as ApiSource[]
  return { enabled, direct, isDirect: (id: string) => direct.includes(id as ApiSource) }
}

const textarea =
  'w-full rounded-md border border-stone-300 bg-white px-3 py-2 font-mono text-sm dark:border-stone-700 dark:bg-stone-900'

function useLastJob(kind: Job['kind']) {
  const { project } = useProjectContext()
  const jobs = useRecentJobs(project.id)
  return jobs.data?.find((j) => j.kind === kind && j.status === 'done')
}

/** Texto de uma correção (`código` ou `código: detalhe`); campos do detalhe viram o nome na tela. */
function useFixText() {
  const { t } = useTranslation()
  return (fix: string) => {
    const [code, ...rest] = fix.split(': ')
    const detail = rest
      .join(': ')
      .split(', ')
      .map((d) => t(`sources.field_${d}`, { defaultValue: d }))
      .join(', ')
    return t(`sources.fix_${code}`, { detail, defaultValue: fix })
  }
}

function Corrections({ items }: { items: string[] }) {
  const { t } = useTranslation()
  const text = useFixText()
  if (!items.length) return null
  return (
    <div
      role="status"
      className="rounded-md bg-amber-50 p-3 text-sm text-amber-800 dark:bg-amber-950 dark:text-amber-200"
    >
      <p className="font-medium">{t('sources.fixed_title')}</p>
      <ul className="list-disc pl-5">
        {items.map((f) => (
          <li key={f}>{text(f)}</li>
        ))}
      </ul>
    </div>
  )
}

function LastSearch() {
  const { t } = useTranslation()
  const job = useLastJob('api_search')
  if (!job) return null
  const r = job.result as {
    source: string
    found: number
    imported: number
    truncated: boolean
    corrections?: string[]
  }
  return (
    <div className="space-y-2">
      <p className="text-sm text-stone-600 dark:text-stone-400">
        {t('sources.last_search', { source: r.source, imported: r.imported, found: r.found })}
        {r.truncated && ` ${t('sources.last_truncated')}`}
      </p>
      <Corrections items={r.corrections ?? []} />
    </div>
  )
}

function LastSnowball() {
  const { t } = useTranslation()
  const job = useLastJob('snowball')
  if (!job) return null
  const r = job.result as {
    seeds: number
    matched: number
    already_in_project: number
    not_found?: string[]
    searches: { direction: string; imported: number }[]
  }
  return (
    <div className="space-y-1 rounded-md bg-stone-50 p-3 text-sm dark:bg-stone-900">
      <p className="font-medium">{t('sources.last_snowball')}</p>
      {r.searches.map((s, i) => (
        <p key={i}>{t(`sources.result_${s.direction}`, { count: s.imported })}</p>
      ))}
      <p className="text-stone-500">
        {t('sources.result_matched', { matched: r.matched, seeds: r.seeds })}
        {r.already_in_project > 0 && ` ${t('sources.result_known', { count: r.already_in_project })}`}
      </p>
      {r.not_found && r.not_found.length > 0 && (
        <p className="text-amber-700 dark:text-amber-300">
          {t('sources.result_not_found', { list: r.not_found.join('; ') })}
        </p>
      )}
    </div>
  )
}

function Translate({ query, onUse }: { query: string; onUse: (source: ApiSource, q: string) => void }) {
  const { t } = useTranslation()
  const { project } = useProjectContext()
  const { translate } = useSourceActions(project.id)
  const bases = useProjectBases()
  // Por padrão, a primeira base escolhida que só entra por arquivo (é a que precisa de tradução)
  const targets = bases.enabled
  const [chosen, setChosen] = useState('')
  const target = targets.includes(chosen)
    ? chosen
    : (targets.find((x) => !bases.isDirect(x)) ?? targets[0] ?? '')
  const result = translate.data
  return (
    <details className="rounded-md border border-stone-200 p-3 dark:border-stone-800">
      <summary className="cursor-pointer text-sm font-medium">{t('sources.translate_title')}</summary>
      <div className="mt-3 space-y-3">
        <p className="text-sm text-stone-500">{t('sources.translate_hint')}</p>
        <div className="flex flex-wrap items-end gap-2">
          <Field label={t('sources.target')}>
            <Select value={target} onChange={(e) => setChosen(e.target.value)}>
              {targets.map((x) => (
                <option key={x} value={x}>
                  {t(`sources.db_${x}`)}
                </option>
              ))}
            </Select>
          </Field>
          <Button
            variant="ghost"
            className="border border-stone-300 dark:border-stone-700"
            disabled={!query.trim() || !target || translate.isPending}
            onClick={() => translate.mutate({ query, target })}
          >
            {translate.isPending ? t('sources.translating') : t('sources.translate')}
          </Button>
        </div>
        <ErrorText error={translate.error} />
        {result && (
          <div className="space-y-2">
            <textarea readOnly rows={4} className={textarea} value={result.query} aria-label={t('sources.translated')} />
            {result.notes.length > 0 && (
              <ul className="list-disc pl-5 text-sm text-stone-600 dark:text-stone-400">
                {result.notes.map((n, i) => (
                  <li key={i}>{n}</li>
                ))}
              </ul>
            )}
            <p className="text-xs text-amber-700 dark:text-amber-300">
              {t('sources.translate_review', { model: result.model })}
            </p>
            <div className="flex flex-wrap gap-2">
              <Button variant="ghost" onClick={() => void navigator.clipboard?.writeText(result.query)}>
                {t('sources.copy')}
              </Button>
              {bases.isDirect(translate.variables?.target ?? '') && (
                <Button
                  variant="ghost"
                  onClick={() => onUse(translate.variables!.target as ApiSource, result.query)}
                >
                  {t('sources.use_here')}
                </Button>
              )}
            </div>
          </div>
        )}
      </div>
    </details>
  )
}

function SearchAssistant({ onUse }: { onUse: (source: ApiSource, q: string) => void }) {
  const { t } = useTranslation()
  const { project } = useProjectContext()
  const { assist, resetAssist } = useSourceActions(project.id)
  const bases = useProjectBases()
  const chat = useAssistChat(project.id)
  const saved: AssistTurn[] = chat.data?.messages ?? []
  const [text, setText] = useState('')
  // A fala enviada fica na tela enquanto a IA responde
  const [sending, setSending] = useState<string | null>(null)
  const turns: AssistTurn[] = sending ? [...saved, { role: 'user', content: sending }] : saved

  const send = () => {
    const content = text.trim()
    if (!content || assist.isPending) return
    setSending(content)
    setText('')
    assist.mutate([...saved, { role: 'user', content }], {
      // Devolve a mensagem ao campo para a pessoa tentar de novo
      onError: () => setText(content),
      onSettled: () => setSending(null),
    })
  }

  return (
    <section className="space-y-3 rounded-md border border-brand-200 p-3 dark:border-brand-800">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="font-medium">{t('sources.assist_title')}</h3>
          <p className="text-sm text-stone-500">{t('sources.assist_intro')}</p>
          <p className="text-xs text-stone-500">
            {chat.isLoading ? t('sources.assist_loading') : t('sources.assist_saved')}
          </p>
        </div>
        {turns.length > 0 && (
          <Button
            variant="ghost"
            disabled={resetAssist.isPending || assist.isPending}
            onClick={() => {
              resetAssist.mutate()
              assist.reset()
            }}
          >
            {t('sources.assist_reset')}
          </Button>
        )}
      </div>
      {turns.length > 0 && (
        <ul className="space-y-3">
          {turns.map((turn, i) => (
            <li
              key={i}
              className={`space-y-2 rounded-md p-3 text-sm ${
                turn.role === 'user' ? 'bg-stone-100 dark:bg-stone-800' : 'bg-brand-50 dark:bg-brand-900/30'
              }`}
            >
              <p className="text-xs font-medium text-stone-500">
                {turn.role === 'user' ? t('sources.assist_you') : t('sources.assist_ai')}
              </p>
              <p className="whitespace-pre-line">{turn.content}</p>
              {turn.strategies?.map((st) => (
                <div key={st.base} className="space-y-1 rounded-md border border-stone-200 bg-white p-2 dark:border-stone-700 dark:bg-stone-900">
                  <p className="text-xs font-medium">{t(`sources.db_${st.base}`, { defaultValue: st.base })}</p>
                  <textarea readOnly rows={3} className={textarea} value={st.query} aria-label={st.base} />
                  {st.notes.length > 0 && (
                    <ul className="list-disc pl-5 text-xs text-stone-600 dark:text-stone-400">
                      {st.notes.map((n, k) => (
                        <li key={k}>{n}</li>
                      ))}
                    </ul>
                  )}
                  <div className="flex flex-wrap gap-2">
                    <Button variant="ghost" onClick={() => void navigator.clipboard?.writeText(st.query)}>
                      {t('sources.copy')}
                    </Button>
                    {bases.isDirect(st.base) && (
                      <Button variant="ghost" onClick={() => onUse(st.base as ApiSource, st.query)}>
                        {t('sources.use_here')}
                      </Button>
                    )}
                  </div>
                </div>
              ))}
              {turn.model && turn.strategies?.length ? (
                <p className="text-xs text-amber-700 dark:text-amber-300">
                  {t('sources.translate_review', { model: turn.model })}
                </p>
              ) : null}
            </li>
          ))}
        </ul>
      )}
      <textarea
        rows={3}
        className={`${textarea} font-sans`}
        aria-label={t('sources.assist_title')}
        placeholder={turns.length ? t('sources.assist_reply_placeholder') : t('sources.assist_placeholder')}
        value={text}
        disabled={assist.isPending}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
            e.preventDefault()
            send()
          }
        }}
      />
      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={send} disabled={!text.trim() || assist.isPending}>
          {assist.isPending ? t('sources.assist_thinking') : t('sources.assist_send')}
        </Button>
        <span className="text-xs text-stone-500">{t('sources.assist_hint')}</span>
      </div>
      {assist.isPending && <p className="text-xs text-stone-500">{t('sources.assist_wait')}</p>}
      <ErrorText error={assist.error} />
    </section>
  )
}

export function ApiSearchCard() {
  const { t, i18n } = useTranslation()
  const { project } = useProjectContext()
  const { preview, search } = useSourceActions(project.id)
  const fieldInfo = useSourceFields(project.id)
  const bases = useProjectBases()
  const [picked, setPicked] = useState<ApiSource>('pubmed')
  // Se a base marcada saiu da seleção do projeto, vale a primeira que sobrou
  const source: ApiSource = bases.direct.includes(picked) ? picked : (bases.direct[0] ?? picked)
  const setSource = setPicked
  // Só bases que entram por arquivo: sobra o assistente e a tradução da estratégia
  const noDirect = bases.enabled.length > 0 && bases.direct.length === 0
  const [mode, setMode] = useState<'builder' | 'text'>('builder')
  const [rows, setRows] = useState<SearchRow[]>([emptyRow()])
  const [query, setQuery] = useState('')
  const [limit, setLimit] = useState(5000)
  const p = preview.data
  const fmt = (n: number) => n.toLocaleString(i18n.language)
  const usedRows = rows.filter((r) => r.term.trim())
  const hasTerms = mode === 'builder' ? usedRows.length > 0 : !!query.trim()
  const payload = mode === 'builder' ? { source, rows: usedRows } : { source, query }

  const changeQuery = (q: string) => {
    setQuery(q)
    preview.reset()
    search.reset()
  }
  const changeRows = (r: SearchRow[]) => {
    setRows(r)
    preview.reset()
    search.reset()
  }

  return (
    <Card className="space-y-4">
      <div>
        <h2 className="font-semibold">{t('sources.title')}</h2>
        <p className="text-sm text-stone-500">{t('sources.hint')}</p>
        <p className="text-xs text-stone-500">{t('sources.no_direct')}</p>
      </div>
      <SearchAssistant
        onUse={(s, q) => {
          setSource(s)
          setMode('text')
          changeQuery(q)
        }}
      />
      {noDirect && (
        <div className="space-y-2">
          <p className="rounded-md border border-amber-300 p-3 text-sm dark:border-amber-700">
            {t('sources.no_direct_chosen')}
          </p>
          <textarea
            rows={4}
            aria-label={t('import.query')}
            className={textarea}
            value={query}
            onChange={(e) => changeQuery(e.target.value)}
          />
        </div>
      )}
      {!noDirect && (
        <>
          <div className="grid gap-4 sm:grid-cols-[14rem_1fr]">
            <Field label={t('sources.source')}>
              <Select
                value={source}
                onChange={(e) => {
                  setSource(e.target.value as ApiSource)
                  preview.reset()
                  search.reset()
                }}
              >
                {bases.direct.map((s) => (
                  <option key={s} value={s}>
                    {t(`sources.db_${s}`)}
                  </option>
                ))}
              </Select>
            </Field>
            <p className="self-end pb-2 text-xs text-stone-500">
              {t(mode === 'builder' ? 'sources.builder_hint' : `sources.syntax_${source}`)}
            </p>
          </div>
          <div className="space-y-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-sm font-medium">{t('import.query')}</span>
              <div role="tablist" className="inline-flex rounded-md border border-stone-300 p-0.5 dark:border-stone-700">
                {(['builder', 'text'] as const).map((m) => (
                  <button
                    key={m}
                    role="tab"
                    type="button"
                    aria-selected={m === mode}
                    onClick={() => {
                      setMode(m)
                      preview.reset()
                      search.reset()
                    }}
                    className={`rounded px-3 py-1 text-sm ${m === mode ? 'bg-brand-600 text-white' : 'text-stone-600 hover:bg-stone-100 dark:text-stone-300 dark:hover:bg-stone-800'}`}
                  >
                    {t(`sources.mode_${m}`)}
                  </button>
                ))}
              </div>
            </div>
            {mode === 'builder' ? (
              <SearchBuilder rows={rows} onChange={changeRows} info={fieldInfo.data?.[source]} />
            ) : (
              <textarea
                rows={4}
                aria-label={t('import.query')}
                className={textarea}
                value={query}
                onChange={(e) => changeQuery(e.target.value)}
              />
            )}
          </div>
          <div className="flex flex-wrap items-end gap-3">
            <Button
              variant="ghost"
              className="border border-stone-300 dark:border-stone-700"
              disabled={!hasTerms || preview.isPending}
              onClick={() => preview.mutate(payload)}
            >
              {preview.isPending ? t('sources.counting') : t('sources.count')}
            </Button>
            <Field label={t('sources.limit')}>
              <Input
                type="number"
                min={1}
                max={p?.max}
                className="w-32"
                value={limit}
                onChange={(e) => setLimit(Math.max(1, Number(e.target.value) || 1))}
              />
            </Field>
            <Button
              disabled={!hasTerms || search.isPending || search.isSuccess}
              onClick={() => search.mutate({ ...payload, limit })}
            >
              {t('sources.import')}
            </Button>
          </div>
          <ErrorText error={preview.error ?? search.error} />
          {search.isSuccess && (
            <p role="status" className="text-sm text-brand-700 dark:text-brand-100">
              {t('sources.started')}
            </p>
          )}
          {!p && <LastSearch />}
          {p && (
            <div className="space-y-2 rounded-md bg-stone-50 p-3 text-sm dark:bg-stone-900">
              <p className="font-medium">{t('sources.found', { count: p.count, n: fmt(p.count) })}</p>
              {p.count > Math.min(limit, p.max) && (
                <p className="text-amber-700 dark:text-amber-300">
                  {t('sources.over_limit', { limit: fmt(Math.min(limit, p.max)) })}
                </p>
              )}
              <Corrections items={p.corrections} />
              {p.warnings.length > 0 && (
                <div className="text-amber-700 dark:text-amber-300">
                  <p>{t('sources.ignored')}</p>
                  <ul className="list-disc pl-5">
                    {p.warnings.map((w, i) => (
                      <li key={i}>{w}</li>
                    ))}
                  </ul>
                </div>
              )}
              {p.translation && (
                <details>
                  <summary className="cursor-pointer text-stone-500">{t('sources.translation')}</summary>
                  <p className="mt-1 break-words font-mono text-xs">{p.translation}</p>
                </details>
              )}
              {p.sample.length > 0 && (
                <>
                  <p className="text-stone-500">{t('sources.sample')}</p>
                  <ol className="list-decimal space-y-1 pl-5">
                    {p.sample.map((r, i) => (
                      <li key={i}>
                        <span className="font-medium">{r.title || t('records.no_title')}</span>
                        <span className="text-stone-500">
                          {' '}
                          · {[r.authors[0], r.year, r.journal].filter(Boolean).join(' · ')}
                        </span>
                      </li>
                    ))}
                  </ol>
                </>
              )}
            </div>
          )}
        </>
      )}
      <Translate
        query={mode === 'builder' && !noDirect ? (p?.strategy ?? '') : query}
        onUse={(s, q) => {
          setSource(s)
          setMode('text')
          changeQuery(q)
        }}
      />
    </Card>
  )
}

export function SnowballCard() {
  const { t } = useTranslation()
  const { project } = useProjectContext()
  const info = useSnowballInfo(project.id)
  const { snowball } = useSourceActions(project.id)
  const [direction, setDirection] = useState<'both' | 'backward' | 'forward'>('both')
  const included = info.data?.included ?? 0
  return (
    <Card className="space-y-4">
      <div>
        <h2 className="font-semibold">{t('sources.snowball_title')}</h2>
        <p className="text-sm text-stone-500">{t('sources.snowball_hint')}</p>
      </div>
      <p className="text-sm">
        {included > 0 ? t('sources.seeds', { count: included }) : t('sources.no_seeds')}
      </p>
      <fieldset className="space-y-2">
        <legend className="sr-only">{t('sources.direction')}</legend>
        {(['both', 'backward', 'forward'] as const).map((d) => (
          <label key={d} className="flex items-start gap-2 text-sm">
            <input
              type="radio"
              name="snowball-direction"
              className="mt-1 accent-brand-600"
              checked={direction === d}
              onChange={() => setDirection(d)}
            />
            <span>
              <span className="font-medium">{t(`sources.dir_${d}`)}</span>
              <span className="block text-xs text-stone-500">{t(`sources.dir_${d}_hint`)}</span>
            </span>
          </label>
        ))}
      </fieldset>
      <ErrorText error={snowball.error} />
      {snowball.isSuccess && (
        <p role="status" className="text-sm text-brand-700 dark:text-brand-100">
          {t('sources.started')}
        </p>
      )}
      <Button
        disabled={included === 0 || snowball.isPending || info.data?.enabled === false}
        onClick={() => snowball.mutate({ direction })}
      >
        {t('sources.snowball_start')}
      </Button>
      <LastSnowball />
    </Card>
  )
}
