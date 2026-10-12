import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, NavLink, Outlet, useParams } from 'react-router-dom'
import { useMe, useProject } from '../../api/hooks'
import { useActiveJobs, useCancelJob, useSummary } from '../../api/records'
import { pillBar, pillItem } from '../../components/pills'
import { CriteriaDrawer } from '../../components/CriteriaDrawer'
import type { ProjectContext } from './context'
import { projectTabs } from './tabs'

function JobBanner({ pid, canStop }: { pid: string; canStop: boolean }) {
  const { t } = useTranslation()
  const { data } = useActiveJobs(pid)
  const cancel = useCancelJob(pid)
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
            {job.status === 'cancelling'
              ? t('jobs.cancelling', { label })
              : job.total > 0
                ? t('jobs.progress', { label, done: job.progress, total: job.total })
                : t('jobs.running', { label })}
            {canStop && job.kind === 'ai_screen' && job.status !== 'cancelling' && (
              <button
                type="button"
                onClick={() => cancel.mutate(job.id)}
                disabled={cancel.isPending}
                className="ml-auto rounded-md border border-red-300 px-2 py-0.5 text-xs font-medium text-red-700 hover:bg-red-50 disabled:opacity-50 dark:border-red-800 dark:text-red-300 dark:hover:bg-red-950"
              >
                {t('jobs.stop')}
              </button>
            )}
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
  const [criteria, setCriteria] = useState(false)

  if (project.isLoading) return <p className="text-stone-500">{t('app.loading')}</p>
  if (!project.data) return <p>{t('projects.not_found')}</p>

  const p = project.data
  const canManage = p.my_role === 'lead' || !!me?.is_admin
  const pending = summary.data?.pending_groups ?? 0
  const { workflow } = projectTabs(t, canManage, pending)
  const renderTabs = (tabs: { to: string; label: string; end?: boolean; badge?: number }[]) =>
    tabs.map((tab) => (
      <li key={tab.to}>
        <NavLink
          to={tab.to}
          end={tab.end}
          className={({ isActive }) => pillItem(isActive)}
        >
          {tab.label}
          {!!tab.badge && (
            <span className="rounded-full bg-amber-100 px-2 text-xs text-amber-800 dark:bg-amber-900 dark:text-amber-100">
              {tab.badge}
            </span>
          )}
        </NavLink>
      </li>
    ))

  return (
    <div className="space-y-6">
      <div>
        <Link to="/" className="text-sm text-brand-600 dark:text-brand-300 hover:underline">
          ← {t('projects.back')}
        </Link>
        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1">
          <h1 className="text-2xl font-semibold">{p.title}</h1>
          <span className="rounded-full bg-stone-200 px-2.5 py-0.5 text-xs text-stone-700 dark:bg-stone-800 dark:text-stone-300">
            {t(`review_type.${p.review_type}`)}
          </span>
          <button
            type="button"
            onClick={() => setCriteria(true)}
            className="ml-auto rounded-md border border-stone-300 px-3 py-1.5 text-sm text-stone-700 hover:bg-stone-100 dark:border-stone-700 dark:text-stone-300 dark:hover:bg-stone-800"
          >
            {t('criteria_drawer.open')}
          </button>
          {p.my_role && (
            <span className="rounded-full bg-brand-100 px-2.5 py-0.5 text-xs text-brand-700 dark:bg-brand-700/30 dark:text-brand-100">
              {t(`role.${p.my_role}`)}
            </span>
          )}
        </div>
      </div>
      <nav aria-label={p.title} className="-mx-4 overflow-x-auto px-4 pb-1">
        <div className={`${pillBar} w-max min-w-full`}>
          <ul className="flex items-center gap-1">{renderTabs(workflow)}</ul>
        </div>
      </nav>
      <CriteriaDrawer pid={id} open={criteria} onClose={() => setCriteria(false)} canManage={canManage} />
      <JobBanner pid={id} canStop={canManage} />
      <Outlet context={{ project: p, canManage } satisfies ProjectContext} />
    </div>
  )
}
