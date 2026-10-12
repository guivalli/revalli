import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { useScreeningSettings } from '../api/screening'
import type { CriterionItem } from '../api/types'
import { Drawer } from './Drawer'

function List({ title, text, items }: { title: string; text: string; items: CriterionItem[] }) {
  const { t } = useTranslation()
  const empty = !text.trim() && items.length === 0
  return (
    <section className="space-y-2">
      <h3 className="text-sm font-semibold">{title}</h3>
      {empty && <p className="text-sm text-stone-500">{t('criteria_drawer.none')}</p>}
      {text.trim() && <p className="whitespace-pre-line text-sm">{text}</p>}
      {items.length > 0 && (
        <ul className="space-y-2">
          {items.map((c) => (
            <li key={c.name} className="rounded-md border border-stone-200 p-3 text-sm dark:border-stone-700">
              <p className="font-medium">{c.name}</p>
              {c.definition && <p className="text-stone-600 dark:text-stone-400">{c.definition}</p>}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

/** Critérios de seleção à mão em qualquer aba, sem sair da tela em que a pessoa está. */
export function CriteriaDrawer({
  pid,
  open,
  onClose,
  canManage,
}: {
  pid: string
  open: boolean
  onClose: () => void
  canManage: boolean
}) {
  const { t } = useTranslation()
  const { data } = useScreeningSettings(pid)
  return (
    <Drawer open={open} onClose={onClose} side="right" title={t('criteria_drawer.title')}>
      <div className="space-y-6 p-4">
        {data ? (
          <>
            <List
              title={t('criteria_drawer.include')}
              text={data.inclusion_criteria}
              items={data.criteria_items.filter((c) => c.kind === 'include')}
            />
            <List
              title={t('criteria_drawer.exclude')}
              text={data.exclusion_criteria}
              items={data.criteria_items.filter((c) => c.kind === 'exclude')}
            />
          </>
        ) : (
          <p className="text-sm text-stone-500">{t('app.loading')}</p>
        )}
        {canManage && (
          <Link
            to="protocolo"
            onClick={onClose}
            className="inline-block text-sm text-brand-600 dark:text-brand-300 underline"
          >
            {t('criteria_drawer.edit')}
          </Link>
        )}
      </div>
    </Drawer>
  )
}
