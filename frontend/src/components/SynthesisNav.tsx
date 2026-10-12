import { useTranslation } from 'react-i18next'
import { NavLink } from 'react-router-dom'
import { pillBar, pillItem } from './pills'

export function SynthesisNav({ pid }: { pid: string }) {
  const { t } = useTranslation()
  const items = [
    { to: `/projetos/${pid}/sintese`, label: t('synthesis.coding'), end: true },
    { to: `/projetos/${pid}/sintese/meta`, label: t('synthesis.meta') },
    { to: `/projetos/${pid}/sintese/grade`, label: t('synthesis.grade') },
    { to: `/projetos/${pid}/sintese/lacunas`, label: t('synthesis.gaps') },
  ]
  return (
    <nav className={pillBar}>
      {items.map((i) => (
        <NavLink
          key={i.to}
          to={i.to}
          end={i.end}
          className={({ isActive }) => pillItem(isActive)}
        >
          {i.label}
        </NavLink>
      ))}
    </nav>
  )
}
