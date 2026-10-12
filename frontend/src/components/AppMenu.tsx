import { useTranslation } from 'react-i18next'
import { NavLink, useMatch } from 'react-router-dom'
import { useLogout, useMe, useProject, useProjects } from '../api/hooks'
import { useSummary } from '../api/records'
import { projectTabs, type Tab } from '../pages/project/tabs'
import { Drawer } from './Drawer'

const item = (active: boolean) =>
  `flex items-center justify-between gap-2 rounded-md px-3 py-2 text-sm transition ${
    active
      ? 'bg-brand-50 font-medium text-brand-700 dark:bg-brand-900/30 dark:text-brand-100'
      : 'text-stone-700 hover:bg-stone-100 dark:text-stone-300 dark:hover:bg-stone-800'
  }`

function Group({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1 px-3 py-3">
      <p className="px-3 pb-1 text-xs font-semibold uppercase tracking-wide text-stone-500">{title}</p>
      {children}
    </div>
  )
}

function ProjectItems({ base, tabs, onNavigate }: { base: string; tabs: Tab[]; onNavigate: () => void }) {
  return (
    <>
      {tabs.map((tab) => (
        <NavLink
          key={tab.to}
          to={tab.to ? `${base}/${tab.to}` : base}
          end={tab.end}
          onClick={onNavigate}
          className={({ isActive }) => item(isActive)}
        >
          {tab.label}
          {!!tab.badge && (
            <span className="rounded-full bg-amber-100 px-2 text-xs text-amber-800 dark:bg-amber-900 dark:text-amber-100">
              {tab.badge}
            </span>
          )}
        </NavLink>
      ))}
    </>
  )
}

/** Menu lateral do aplicativo: início, revisões e, dentro de uma revisão, todas as suas abas. */
export function AppMenu({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t } = useTranslation()
  const { data: me } = useMe()
  const projects = useProjects()
  const logout = useLogout()
  const match = useMatch('/projetos/:id/*')
  const pid = match?.params.id ?? ''
  const project = useProject(pid)
  const summary = useSummary(pid)
  const canManage = project.data?.my_role === 'lead' || !!me?.is_admin
  const { workflow, setup } = projectTabs(t, canManage, summary.data?.pending_groups ?? 0)

  return (
    <Drawer open={open} onClose={onClose} title={t('app.name')}>
      <nav className="divide-y divide-stone-100 dark:divide-stone-800">
        <Group title={t('menu.home')}>
          <NavLink to="/" end onClick={onClose} className={({ isActive }) => item(isActive)}>
            {t('menu.all_reviews')}
          </NavLink>
          <NavLink to="/?nova=1" onClick={onClose} className={() => item(false)}>
            + {t('home.create')}
          </NavLink>
        </Group>

        {pid && project.data && (
          <>
            <Group title={project.data.title}>
              <ProjectItems base={`/projetos/${pid}`} tabs={workflow} onNavigate={onClose} />
            </Group>
            <Group title={t('menu.setup')}>
              <ProjectItems base={`/projetos/${pid}`} tabs={setup} onNavigate={onClose} />
            </Group>
          </>
        )}

        {(projects.data?.length ?? 0) > 0 && (
          <Group title={t('menu.reviews')}>
            {projects.data?.slice(0, 8).map((p) => (
              <NavLink
                key={p.id}
                to={`/projetos/${p.id}`}
                onClick={onClose}
                className={() => item(p.id === pid)}
              >
                <span className="truncate">{p.title}</span>
              </NavLink>
            ))}
          </Group>
        )}

        <Group title={t('menu.account')}>
          {me?.is_admin && (
            <NavLink to="/ia" onClick={onClose} className={({ isActive }) => item(isActive)}>
              {t('app.ai_settings')}
            </NavLink>
          )}
          <NavLink to="/conta" onClick={onClose} className={({ isActive }) => item(isActive)}>
            {me?.full_name}
          </NavLink>
          <button
            type="button"
            onClick={() => logout.mutate()}
            className="w-full rounded-md px-3 py-2 text-left text-sm text-stone-700 hover:bg-stone-100 dark:text-stone-300 dark:hover:bg-stone-800"
          >
            {t('app.logout')}
          </button>
        </Group>
      </nav>
    </Drawer>
  )
}
