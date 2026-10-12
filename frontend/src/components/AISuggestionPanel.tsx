import { useTranslation } from 'react-i18next'
import type { AISuggestion, TagItem } from '../api/types'
import { Button } from './ui'

const tone = {
  include: 'border-emerald-300 bg-emerald-50 dark:border-emerald-800 dark:bg-emerald-950/40',
  exclude: 'border-red-300 bg-red-50 dark:border-red-800 dark:bg-red-950/40',
  maybe: 'border-amber-300 bg-amber-50 dark:border-amber-800 dark:bg-amber-950/40',
}

const mark = { met: '✓', violated: '✗', unclear: '?' }

/** Sugestão da IA para o registro aberto: decisão, motivo, critérios e até 4 etiquetas. */
export function AISuggestionPanel({
  s,
  vocabulary,
  labels,
  onLabels,
}: {
  s: AISuggestion
  vocabulary: TagItem[]
  labels: string[]
  onLabels: (next: string[]) => void
}) {
  const { t } = useTranslation()
  const known = new Set(vocabulary.map((v) => v.name.toLowerCase()))
  const has = (tag: string) => labels.some((l) => l.toLowerCase() === tag.toLowerCase())
  const toggle = (tag: string) =>
    onLabels(has(tag) ? labels.filter((l) => l.toLowerCase() !== tag.toLowerCase()) : [...labels, tag])
  const missing = s.tags.filter((tag) => !has(tag))
  return (
    <div className={`space-y-2 rounded-md border p-3 text-sm ${tone[s.decision]}`}>
      <p className="font-medium">
        {t('ai.chip', { decision: t(`decision.${s.decision}`) })}
        {s.confidence != null && ` · ${Math.round(s.confidence * 100)}%`}
      </p>
      {s.justification && <p>{s.justification}</p>}
      {s.decision === 'exclude' && s.exclusion_reason && (
        <p className="text-xs font-medium">{t('ai_panel.reason', { reason: s.exclusion_reason })}</p>
      )}
      {s.criteria.length > 0 && (
        <ul className="space-y-0.5 text-xs">
          {s.criteria.map((c, i) => (
            <li key={i}>
              <span className="mr-1 font-mono">{mark[c.status]}</span>
              {c.criterion}
            </li>
          ))}
        </ul>
      )}
      {s.tags.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs font-medium">{t('ai_panel.tags')}</p>
          <ul className="flex flex-wrap gap-1">
            {s.tags.map((tag) => (
              <li key={tag}>
                <button
                  type="button"
                  onClick={() => toggle(tag)}
                  aria-pressed={has(tag)}
                  title={known.has(tag.toLowerCase()) ? undefined : t('ai_panel.new_tag')}
                  className={`rounded-full border px-2 py-0.5 text-xs ${
                    has(tag)
                      ? 'border-brand-600 bg-brand-600 text-white'
                      : 'border-stone-400 bg-white dark:bg-stone-900'
                  } ${known.has(tag.toLowerCase()) ? '' : 'border-dashed'}`}
                >
                  {has(tag) ? '✓ ' : '+ '}
                  {tag}
                </button>
              </li>
            ))}
          </ul>
          {missing.length > 1 && (
            <Button variant="ghost" className="px-2 py-1 text-xs" onClick={() => onLabels([...labels, ...missing])}>
              {t('ai_panel.use_all')}
            </Button>
          )}
        </div>
      )}
    </div>
  )
}
