import { useTranslation } from 'react-i18next'
import { useDatabases, useSaveDatabases } from '../../api/sources'
import type { DatabaseInfo } from '../../api/types'
import { Button, Card, ErrorText } from '../../components/ui'
import { useProjectContext } from './context'

const PACKS = ['health', 'rehab', 'psychology', 'education', 'social', 'computing'] as const

function Group({
  title,
  hint,
  items,
  enabled,
  disabled,
  onToggle,
}: {
  title: string
  hint?: string
  items: DatabaseInfo[]
  enabled: string[]
  disabled: boolean
  onToggle: (id: string, on: boolean) => void
}) {
  const { t } = useTranslation()
  return (
    <fieldset className="space-y-2">
      <legend className="text-sm font-medium">{title}</legend>
      {hint && <p className="text-xs text-stone-500">{hint}</p>}
      <div className="grid gap-x-4 gap-y-1 sm:grid-cols-2">
        {items.map((d) => (
          <label key={d.id} className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={enabled.includes(d.id)}
              disabled={disabled}
              onChange={(e) => onToggle(d.id, e.target.checked)}
            />
            {t(`sources.db_${d.id}`)}
          </label>
        ))}
      </div>
    </fieldset>
  )
}

/** Escolha das bases do projeto: enxuga a busca direta, a tradução e o assistente de busca. */
export function DatabasesCard() {
  const { t } = useTranslation()
  const { project } = useProjectContext()
  const databases = useDatabases(project.id)
  const save = useSaveDatabases(project.id)
  const data = databases.data
  if (!data) return null
  const enabled = data.enabled
  const change = (next: string[]) => {
    if (next.length > 0) save.mutate(next)
  }
  const toggle = (id: string, on: boolean) =>
    change(on ? [...enabled, id] : enabled.filter((x) => x !== id))
  const names = enabled.map((id) => t(`sources.db_${id}`)).join(', ')
  const direct = data.catalog.filter((d) => d.direct)
  const files = data.catalog.filter((d) => !d.direct)
  return (
    <Card>
      <details open={!data.saved}>
        <summary className="cursor-pointer">
          <span className="font-semibold">{t('sources.databases_title')}</span>
          <span className="ml-2 text-sm text-stone-500">
            {data.saved
              ? t('sources.databases_chosen', { count: enabled.length })
              : t('sources.databases_default')}
          </span>
        </summary>
        <div className="mt-3 space-y-4">
          <p className="text-sm text-stone-500">{t('sources.databases_hint')}</p>
          <div className="space-y-2">
            <p className="text-sm font-medium">{t('sources.databases_packs')}</p>
            <p className="text-xs text-stone-500">{t('sources.databases_packs_hint')}</p>
            <div className="flex flex-wrap gap-2">
              {PACKS.filter((k) => data.packs[k]).map((k) => (
                <Button
                  key={k}
                  type="button"
                  variant="ghost"
                  className="border border-stone-300 dark:border-stone-700"
                  disabled={save.isPending}
                  onClick={() => change(data.packs[k])}
                >
                  {t(`sources.pack_${k}`)}
                </Button>
              ))}
            </div>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <Group
              title={t('sources.databases_direct')}
              items={direct}
              enabled={enabled}
              disabled={save.isPending}
              onToggle={toggle}
            />
            <Group
              title={t('sources.databases_file')}
              hint={t('sources.databases_file_hint')}
              items={files}
              enabled={enabled}
              disabled={save.isPending}
              onToggle={toggle}
            />
          </div>
          {enabled.length === 1 && (
            <p className="text-xs text-stone-500">{t('sources.databases_keep_one')}</p>
          )}
          <p className="text-xs text-stone-500">{t('sources.databases_paid')}</p>
          <ErrorText error={save.error ?? databases.error} />
          <p className="break-words text-xs text-stone-500">{names}</p>
        </div>
      </details>
    </Card>
  )
}
