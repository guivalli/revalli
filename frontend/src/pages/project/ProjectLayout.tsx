import { useTranslation } from 'react-i18next'
import { Link, NavLink, Outlet, useParams } from 'react-router-dom'
import { useMe, useProject } from '../../api/hooks'
import { useActiveJobs, useSummary } from '../../api/records'
import type { ProjectContext } from './context'

function JobBanner({ pid }: { pid: string }) {
  const { t } = useTranslation()
  const { data } = useActiveJobs(pid)
  if (!data?.length) return null
  // Uma linha por tipo de tarefa, mesmo que haja várias na fila
  const byKind = [...new Map(data.map((j) => [j.kind, j])).values()]
  return (
    <div className="space-y-1">
      {byKind.map((job) => {
        const label = t(`jobs.${job.kind}`)
        return (
          <p
            key={job.id}
            role="status"
            className="flex items-center gap-2 rounded-md bg-brand-50 px-3 py-2 text-sm text-brand-700 dark:bg-stone-800 dark:text-brand-100"
          >
            <span className="size-2 animate-pulse rounded-full bg-brand-500" />
            {job.total > 0
              ? t('jobs.progress', { label, done: job.progress, total: job.total })
              : t('jobs.running', { label })}
          </p>
        )
      })}
    </div>
  )
}

export default function ProjectLayout() {
  const { id = '' } = useParams()
  const { t } = useTranslation()
  const { data: me } = useMe()
  const project = useProject(id)
  const summary = useSummary(id)

  if (project.isLoading) return <p className="text-stone-500">{t('app.loading')}</p>
  if (!project.data) return <p>{t('projects.not_found')}</p>

  const p = project.data
  const canManage = p.my_role === 'lead' || !!me?.is_admin
  const pending = summary.data?.pending_groups ?? 0
  const tabs = [
    { to: '', label: t('tabs.overview'), end: true },
    { to: 'referencias', label: t('tabs.records') },
    ...(canManage ? [{ to: 'importar', label: t('tabs.import') }] : []),
    { to: 'duplicatas', label: t('tabs.duplicates'), badge: pending },
    { to: 'triagem', label: t('tabs.screening') },
    { to: 'protocolo', label: t('tabs.protocol') },
    { to: 'ia', label: t('tabs.ai') },
    { to: 'relatorio', label: t('tabs.report') },
    { to: 'membros', label: t('tabs.members') },
  ]

  return (
    <div className="space-y-6">
      <div>
        <Link to="/" className="text-sm text-brand-600 hover:underline">
          ← {t('projects.back')}
        </Link>
        <h1 className="mt-2 text-2xl font-semibold">{p.title}</h1>
        <p className="text-sm text-stone-500">{t(`review_type.${p.review_type}`)}</p>
      </div>
      <nav className="-mx-4 overflow-x-auto px-4">
        <ul className="flex gap-1 border-b border-stone-200 dark:border-stone-800">
          {tabs.map((tab) => (
            <li key={tab.to}>
              <NavLink
                to={tab.to}
                end={tab.end}
                className={({ isActive }) =>
                  `flex items-center gap-2 whitespace-nowrap border-b-2 px-3 py-2 text-sm ${
                    isActive
                      ? 'border-brand-600 font-medium text-brand-700 dark:text-brand-100'
                      : 'border-transparent text-stone-600 hover:text-stone-900 dark:text-stone-400'
                  }`
                }
              >
                {tab.label}
                {!!tab.badge && (
                  <span className="rounded-full bg-amber-100 px-2 text-xs text-amber-800 dark:bg-amber-900 dark:text-amber-100">
                    {tab.badge}
                  </span>
                )}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
      <JobBanner pid={id} />
      <Outlet context={{ project: p, canManage } satisfies ProjectContext} />
    </div>
  )
}
