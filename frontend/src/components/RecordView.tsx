import { useTranslation } from 'react-i18next'
import type { RecordItem } from '../api/types'

export function Badge({ children, tone = 'stone' }: { children: string; tone?: 'stone' | 'amber' | 'brand' }) {
  const tones = {
    stone: 'bg-stone-100 text-stone-700 dark:bg-stone-800 dark:text-stone-300',
    amber: 'bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-100',
    brand: 'bg-brand-50 text-brand-700 dark:bg-stone-800 dark:text-brand-100',
  }
  return <span className={`rounded px-1.5 py-0.5 text-xs ${tones[tone]}`}>{children}</span>
}

export function RecordLinks({ r }: { r: RecordItem }) {
  return (
    <span className="space-x-3 text-xs">
      {r.doi && (
        <a
          className="text-brand-600 hover:underline"
          href={`https://doi.org/${r.doi}`}
          target="_blank"
          rel="noreferrer noopener"
        >
          DOI {r.doi}
        </a>
      )}
      {r.pmid && (
        <a
          className="text-brand-600 hover:underline"
          href={`https://pubmed.ncbi.nlm.nih.gov/${r.pmid}/`}
          target="_blank"
          rel="noreferrer noopener"
        >
          PMID {r.pmid}
        </a>
      )}
    </span>
  )
}

export function RecordDetails({ r }: { r: RecordItem }) {
  const { t } = useTranslation()
  return (
    <div className="space-y-2 text-sm">
      <p className="whitespace-pre-line leading-relaxed">
        {r.abstract || <span className="text-stone-500">{t('records.no_abstract')}</span>}
      </p>
      {r.keywords.length > 0 && (
        <p className="text-xs text-stone-500">
          {t('records.keywords')}: {r.keywords.join('; ')}
        </p>
      )}
      <RecordLinks r={r} />
    </div>
  )
}
