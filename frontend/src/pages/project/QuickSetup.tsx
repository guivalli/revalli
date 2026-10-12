import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { useProjectAI } from '../../api/ai'
import { useScreeningSettings } from '../../api/screening'
import { Button, Section } from '../../components/ui'

interface Step {
  key: string
  done: boolean
  to?: string
  ai?: boolean
  manage?: boolean
}

function dismissedKey(pid: string) {
  return `revalli.setup.${pid}`
}

function readDismissed(pid: string): boolean {
  try {
    return localStorage.getItem(dismissedKey(pid)) === '1'
  } catch {
    return false
  }
}

/** Primeiros passos da revisão. Cada item se marca sozinho a partir dos dados do projeto e
 * leva para a aba certa; os que usam IA vêm com a etiqueta "IA". Some quando tudo está feito. */
export function QuickSetup({
  pid,
  canManage,
  records,
  pendingGroups,
  members,
  screeningStarted,
}: {
  pid: string
  canManage: boolean
  records: number
  pendingGroups: number
  members: number
  screeningStarted: boolean
}) {
  const { t } = useTranslation()
  const settings = useScreeningSettings(pid)
  const ai = useProjectAI(pid)
  const [dismissed, setDismissed] = useState(() => readDismissed(pid))
  if (!settings.data || !ai.data) return null

  const s = settings.data
  const criteria = !!(
    s.inclusion_criteria.trim() ||
    s.exclusion_criteria.trim() ||
    s.criteria_items.length > 0
  )
  const solo = s.reviewers_title_abstract <= 1 && s.reviewers_full_text <= 1
  const steps: Step[] = [
    { key: 'create', done: true },
    { key: 'references', done: records > 0, to: 'importar', ai: true, manage: true },
    { key: 'duplicates', done: records > 0 && pendingGroups === 0, to: 'duplicatas' },
    { key: 'criteria', done: criteria, to: 'protocolo', ai: true, manage: true },
    { key: 'ai', done: ai.data.enabled, to: 'ia', ai: true, manage: true },
    { key: 'team', done: members > 1 || solo, to: 'membros', manage: true },
    { key: 'screen', done: screeningStarted, to: 'triagem' },
  ]
  const done = steps.filter((x) => x.done).length
  if (dismissed || done === steps.length) return null
  const next = steps.find((x) => !x.done)

  const hide = () => {
    setDismissed(true)
    try {
      localStorage.setItem(dismissedKey(pid), '1')
    } catch {
      // Sem armazenamento: some só até recarregar
    }
  }

  return (
    <Section
      title={t('setup.title')}
      actions={
        <>
          <span className="text-sm text-stone-500">{t('setup.progress', { done, total: steps.length })}</span>
          <Button variant="ghost" onClick={hide}>
            {t('setup.hide')}
          </Button>
        </>
      }
    >
      <div
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={steps.length}
        aria-valuenow={done}
        aria-label={t('setup.title')}
        className="mb-4 h-2 overflow-hidden rounded-full bg-stone-200 dark:bg-stone-800"
      >
        <div
          className="h-full rounded-full bg-brand-500 transition-all"
          style={{ width: `${(done / steps.length) * 100}%` }}
        />
      </div>
      <ol className="divide-y divide-stone-100 dark:divide-stone-800">
        {steps.map((step) => (
          <li key={step.key} className="flex items-start gap-3 py-3">
            <span
              aria-hidden
              className={`mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full text-xs ${
                step.done
                  ? 'bg-brand-600 text-white'
                  : 'border border-stone-300 text-transparent dark:border-stone-600'
              }`}
            >
              ✓
            </span>
            <div className="min-w-0 flex-1">
              <p className={`text-sm font-medium ${step.done ? 'text-stone-500 line-through' : ''}`}>
                {t(`setup.${step.key}`)}
                {step.ai && (
                  <span className="ml-2 rounded-full bg-brand-100 px-2 py-0.5 text-[10px] font-semibold uppercase text-brand-700 no-underline dark:bg-brand-700/30 dark:text-brand-100">
                    {t('setup.ai_badge')}
                  </span>
                )}
              </p>
              {!step.done && <p className="text-xs text-stone-500">{t(`setup.${step.key}_hint`)}</p>}
            </div>
            {!step.done && step.to && (!step.manage || canManage) && (
              <Link
                to={step.to}
                className={`shrink-0 rounded-md px-3 py-1.5 text-sm font-medium ${
                  step === next
                    ? 'bg-brand-600 text-white hover:bg-brand-700'
                    : 'border border-stone-300 text-stone-700 hover:bg-stone-100 dark:border-stone-700 dark:text-stone-300 dark:hover:bg-stone-800'
                }`}
              >
                {t('setup.open')}
              </Link>
            )}
          </li>
        ))}
      </ol>
    </Section>
  )
}
