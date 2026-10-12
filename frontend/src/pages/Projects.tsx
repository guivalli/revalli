import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router-dom'
import { useMe, useProjects } from '../api/hooks'
import { NewReviewDialog } from '../components/NewReviewDialog'
import { Button, ErrorText, Section } from '../components/ui'

export default function Projects() {
  const { t, i18n } = useTranslation()
  const { data: me } = useMe()
  const { data, isLoading, error } = useProjects()
  const [params, setParams] = useSearchParams()
  const [creating, setCreating] = useState(params.get('nova') === '1')
  const closeWizard = () => {
    setCreating(false)
    if (params.has('nova')) setParams({}, { replace: true })
  }
  const firstName = me?.full_name?.split(' ')[0] ?? ''
  const date = (iso: string) =>
    new Date(iso).toLocaleDateString(i18n.language, { day: '2-digit', month: 'short', year: 'numeric' })

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-brand-100 bg-gradient-to-r from-brand-50 to-white px-6 py-6 dark:border-brand-800 dark:from-brand-900/70 dark:to-stone-900">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold text-stone-900 dark:text-stone-50">
            {t('home.welcome', { name: firstName })}
          </h1>
          <p className="text-sm text-stone-600 dark:text-stone-300">{t('home.subtitle')}</p>
        </div>
        <Button onClick={() => setCreating(true)} className="gap-2 px-4">
          <span aria-hidden className="text-lg leading-none">
            +
          </span>
          {t('home.create')}
        </Button>
      </div>

      <ErrorText error={error} />
      {isLoading && <p className="text-stone-500">{t('app.loading')}</p>}

      <Section title={t('home.active')}>
        {data && data.length === 0 ? (
          <div className="space-y-3 py-8 text-center">
            <p className="text-3xl" aria-hidden>
              📚
            </p>
            <p className="font-medium">{t('home.empty_title')}</p>
            <p className="mx-auto max-w-md text-sm text-stone-500">{t('home.empty_hint')}</p>
            <Button onClick={() => setCreating(true)}>{t('home.create')}</Button>
          </div>
        ) : (
          <div className="-mx-5 overflow-x-auto px-5">
            <table className="w-full min-w-[34rem] text-sm">
              <thead>
                <tr className="text-left text-stone-500">
                  <th className="py-2 font-normal">{t('home.col_title')}</th>
                  <th className="py-2 font-normal">{t('home.col_created')}</th>
                  <th className="hidden py-2 font-normal md:table-cell">{t('home.col_owner')}</th>
                  <th className="py-2 text-right font-normal">{t('home.col_records')}</th>
                  <th className="hidden py-2 text-right font-normal sm:table-cell">{t('home.col_team')}</th>
                </tr>
              </thead>
              <tbody>
                {data?.map((p) => (
                  <tr
                    key={p.id}
                    className="border-t border-stone-100 transition hover:bg-stone-50 dark:border-stone-800 dark:hover:bg-stone-800/50"
                  >
                    <td className="py-3">
                      <Link to={`/projetos/${p.id}`} className="flex items-center gap-3">
                        <span aria-hidden className="h-8 w-1 rounded-full bg-brand-500" />
                        <span>
                          <span className="block font-medium">{p.title}</span>
                          <span className="block text-xs text-stone-500">
                            {t(`review_type.${p.review_type}`)}
                            {p.my_role && <> · {t(`role.${p.my_role}`)}</>}
                          </span>
                        </span>
                      </Link>
                    </td>
                    <td className="py-3 text-stone-600 dark:text-stone-400">{date(p.created_at)}</td>
                    <td className="hidden py-3 text-stone-600 dark:text-stone-400 md:table-cell">
                      {p.owner_name}
                    </td>
                    <td className="py-3 text-right tabular-nums">{p.record_count.toLocaleString()}</td>
                    <td className="hidden py-3 text-right tabular-nums sm:table-cell">{p.member_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      {creating && <NewReviewDialog onClose={closeWizard} />}
    </div>
  )
}
