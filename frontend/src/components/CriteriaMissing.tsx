import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { ApiError } from '../api/client'

/** Aviso para quando a IA recusa trabalhar porque o projeto não tem critérios. */
export function CriteriaMissing({ error, pid }: { error: unknown; pid: string }) {
  const { t } = useTranslation()
  if (!(error instanceof ApiError) || error.code !== 'criteria_missing') return null
  return (
    <div
      role="alert"
      className="space-y-1 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm dark:border-amber-700 dark:bg-amber-950/40"
    >
      <p>{t('errors.criteria_missing')}</p>
      <Link to={`/projetos/${pid}/protocolo`} className="font-medium text-brand-700 underline dark:text-brand-100">
        {t('protocol_ai.go_protocol')}
      </Link>
    </div>
  )
}
