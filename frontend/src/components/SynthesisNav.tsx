import { useTranslation } from 'react-i18next'
import { NavLink } from 'react-router-dom'

export function SynthesisNav({ pid }: { pid: string }) {
  const { t } = useTranslation()
  const items = [
    { to: `/projetos/${pid}/sintese`, label: t('synthesis.coding'), end: true },
    { to: `/projetos/${pid}/sintese/meta`, label: t('synthesis.meta') },
    { to: `/projetos/${pid}/sintese/grade`, label: t('synthesis.grade') },
  ]
  return (
    <nav className="inline-flex rounded-md border border-stone-300 p-0.5 text-sm dark:border-stone-700">
      {items.map((i) => (
        <NavLink
          key={i.to}
          to={i.to}
          end={i.end}
          className={({ isActive }) =>
            `rounded px-3 py-1 ${isActive ? 'bg-brand-600 text-white' : 'hover:bg-stone-100 dark:hover:bg-stone-800'}`
          }
        >
          {i.label}
        </NavLink>
      ))}
    </nav>
  )
}
