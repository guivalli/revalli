import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { checklistExportUrl, useChecklist, useSaveChecklistEntry } from '../../api/synthesis'
import type { ChecklistEntry, ChecklistFacts, ChecklistStatus } from '../../api/types'
import { Card, ErrorText, Input, Select } from '../../components/ui'
import { CHECKLIST_SECTIONS, type ChecklistKind } from '../../lib/checklists'
import { useProjectContext } from './context'

const STATUS_STYLE: Record<ChecklistStatus, string> = {
  pending: 'border-stone-300 dark:border-stone-700',
  done: 'border-emerald-500 bg-emerald-50 dark:bg-emerald-950',
  na: 'border-stone-300 bg-stone-100 dark:border-stone-700 dark:bg-stone-800',
}

/** Itens em que o ReValli já tem dados do projeto para ajudar a escrever. */
const FACT_ITEMS: Record<ChecklistKind, Record<string, string>> = {
  prisma2020: {
    '6': 'sources',
    '7': 'strategies',
    '8': 'screening',
    '9': 'forms',
    '11': 'rob',
    '16a': 'prisma',
    '27': 'exports',
  },
  prisma_scr: {
    '7': 'sources',
    '8': 'strategies',
    '9': 'screening',
    '10': 'forms',
    '12': 'rob',
    '14': 'prisma',
    '18': 'coding',
  },
}

function useFact() {
  const { t, i18n } = useTranslation()
  return (kind: string, f: ChecklistFacts): string[] => {
    switch (kind) {
      case 'sources': {
        if (!f.searches.length) return [t('checklist.fact_no_sources')]
        const list = f.searches.map((s) =>
          [
            s.method === 'database' ? s.source : `${t(`prisma.method_${s.method}`)} (${s.source})`,
            s.searched_on && new Date(s.searched_on + 'T00:00').toLocaleDateString(i18n.language),
          ]
            .filter(Boolean)
            .join(', '),
        )
        return [t('checklist.fact_sources', { list: list.join('; ') })]
      }
      case 'strategies': {
        const db = f.searches.filter((s) => s.method === 'database')
        return [t('checklist.fact_strategies', { with: db.filter((s) => s.has_query).length, total: db.length })]
      }
      case 'screening': {
        const s = f.screening
        const out = [
          t('checklist.fact_screening', {
            ta: s.reviewers_title_abstract,
            ft: s.reviewers_full_text,
            blind: s.blind ? t('checklist.fact_blind') : t('checklist.fact_not_blind'),
          }),
        ]
        if (f.ai.enabled && (f.ai.calls.screening ?? 0) > 0)
          out.push(
            t('checklist.fact_ai', {
              mode: t(`checklist.fact_ai_${f.ai.mode}`),
              local: f.ai.local_only ? t('checklist.fact_ai_local') : '',
            }),
          )
        return out
      }
      case 'forms': {
        const forms = f.forms.filter((x) => x.kind === 'extraction')
        if (!forms.length) return []
        const list = forms.map((x) => t('checklist.fact_extractors', { name: x.name, count: x.extractors }))
        return [t('checklist.fact_forms', { list: list.join('; ') })]
      }
      case 'rob': {
        const forms = f.forms.filter((x) => x.kind === 'rob')
        if (!forms.length) return [t('checklist.fact_no_rob')]
        const list = forms.map((x) => t('checklist.fact_extractors', { name: x.name, count: x.extractors }))
        return [t('checklist.fact_rob', { list: list.join('; ') })]
      }
      case 'prisma': {
        const p = f.prisma
        return [
          t('checklist.fact_prisma', {
            identified: p.identification.total,
            duplicates: p.identification.duplicates_removed,
            screened: p.screening.screened,
            included: p.included,
          }),
        ]
      }
      case 'coding':
        return f.coding.codes ? [t('checklist.fact_coding', f.coding)] : []
      case 'exports':
        return f.forms.length ? [t('checklist.fact_exports')] : []
      default:
        return []
    }
  }
}

function Item({
  kind,
  entry,
  facts,
  canEdit,
}: {
  kind: ChecklistKind
  entry: ChecklistEntry
  facts: string[]
  canEdit: boolean
}) {
  const { t } = useTranslation()
  const { project } = useProjectContext()
  const save = useSaveChecklistEntry(project.id, kind)
  // Estado local: o que a pessoa digitou vale mesmo antes da resposta do servidor
  const [status, setStatus] = useState(entry.status)
  const [location, setLocation] = useState(entry.location)
  const [note, setNote] = useState(entry.note)
  const [saved, setSaved] = useState({ location: entry.location, note: entry.note })
  const put = (patch: { status?: ChecklistStatus } = {}) => {
    const body = { status: patch.status ?? status, location, note }
    setSaved({ location, note })
    save.mutate({ item: entry.item, body })
  }
  return (
    <li className={`space-y-2 rounded-md border-l-4 p-3 ${STATUS_STYLE[status]}`}>
      <div className="flex flex-wrap items-start gap-3">
        <span className="w-8 shrink-0 font-semibold tabular-nums">{entry.item}</span>
        <p className="min-w-0 flex-1 text-sm">{t(`checklist_items.${kind}.${entry.item}`)}</p>
        <Select
          aria-label={`${t('checklist.title')} ${entry.item}`}
          className="w-40! shrink-0"
          disabled={!canEdit}
          value={status}
          onChange={(e) => {
            const next = e.target.value as ChecklistStatus
            setStatus(next)
            put({ status: next })
          }}
        >
          {(['pending', 'done', 'na'] as const).map((s) => (
            <option key={s} value={s}>
              {t(`checklist.status_${s}`)}
            </option>
          ))}
        </Select>
      </div>
      {facts.length > 0 && (
        <div className="ml-11 space-y-0.5 text-xs text-sky-800 dark:text-sky-300">
          {facts.map((f, i) => (
            <p key={i}>{f}</p>
          ))}
        </div>
      )}
      <div className="ml-11 grid gap-2 sm:grid-cols-2">
        <Input
          aria-label={`${t('checklist.location')} ${entry.item}`}
          placeholder={t('checklist.location')}
          disabled={!canEdit}
          value={location}
          onChange={(e) => setLocation(e.target.value)}
          onBlur={() => location !== saved.location && put()}
        />
        <Input
          aria-label={`${t('checklist.note')} ${entry.item}`}
          placeholder={t('checklist.note')}
          disabled={!canEdit}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          onBlur={() => note !== saved.note && put()}
        />
      </div>
      <ErrorText error={save.error} />
    </li>
  )
}

export function ChecklistSection() {
  const { t } = useTranslation()
  const { project, canManage } = useProjectContext()
  const [kind, setKind] = useState<ChecklistKind>(project.review_type === 'scoping' ? 'prisma_scr' : 'prisma2020')
  const data = useChecklist(project.id, kind)
  const fact = useFact()
  const entries = new Map((data.data?.entries ?? []).map((e) => [e.item, e]))
  const resolved = [...entries.values()].filter((e) => e.status !== 'pending').length
  return (
    <Card className="space-y-4 p-4">
      <div className="flex flex-wrap items-start gap-3">
        <div className="mr-auto">
          <h2 className="font-semibold">{t('checklist.title')}</h2>
          <p className="text-sm text-stone-500">{t('checklist.hint')}</p>
        </div>
        <Select aria-label={t('checklist.title')} className="w-80!" value={kind} onChange={(e) => setKind(e.target.value as ChecklistKind)}>
          {(Object.keys(CHECKLIST_SECTIONS) as ChecklistKind[]).map((k) => (
            <option key={k} value={k}>
              {t(`checklist.kind_${k}`)}
            </option>
          ))}
        </Select>
      </div>
      {data.data && (
        <p className="flex flex-wrap items-center gap-4 text-sm">
          <span>{t('checklist.progress', { done: resolved, total: entries.size })}</span>
          <a className="text-brand-600 hover:underline" href={checklistExportUrl(project.id, kind)}>
            {t('checklist.export')}
          </a>
        </p>
      )}
      {data.data &&
        (Object.entries(CHECKLIST_SECTIONS[kind]) as [string, readonly string[]][]).map(([section, items]) => (
          <section key={section} className="space-y-2">
            <h3 className="text-sm font-semibold tracking-wide text-stone-500 uppercase">
              {t(`checklist.section_${section}`)}
            </h3>
            <ul className="space-y-2">
              {items.map((item) => {
                const entry = entries.get(item)
                if (!entry) return null
                const factKind = FACT_ITEMS[kind][item]
                return (
                  <Item
                    key={`${kind}-${item}`}
                    kind={kind}
                    entry={entry}
                    facts={factKind ? fact(factKind, data.data.facts) : []}
                    canEdit={canManage}
                  />
                )
              })}
            </ul>
          </section>
        ))}
    </Card>
  )
}
