import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { AISuggestion } from '../api/types'

const tone = {
  include: 'border-emerald-300 text-emerald-800 dark:border-emerald-700 dark:text-emerald-200',
  exclude: 'border-red-300 text-red-800 dark:border-red-700 dark:text-red-200',
  maybe: 'border-amber-300 text-amber-800 dark:border-amber-700 dark:text-amber-200',
}

const mark = { met: '✓', violated: '✗', unclear: '?' }

export function AISuggestionChip({ s }: { s: AISuggestion }) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  return (
    <span className="inline-block text-xs">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className={`rounded-md border border-dashed px-2 py-0.5 ${tone[s.decision]}`}
      >
        {t('ai.chip', { decision: t(`decision.${s.decision}`) })}
        {s.confidence != null && ` · ${Math.round(s.confidence * 100)}%`}
      </button>
      {open && (
        <span className="mt-1 block max-w-prose space-y-1 rounded-md bg-stone-50 p-2 text-stone-700 dark:bg-stone-800 dark:text-stone-200">
          <span className="block">{s.justification}</span>
          {s.criteria.map((c, i) => (
            <span key={i} className="block">
              {mark[c.status]} {c.criterion}
            </span>
          ))}
        </span>
      )}
    </span>
  )
}
