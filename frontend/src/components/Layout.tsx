import { Link, Outlet } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useLogout, useMe } from '../api/hooks'
import { LANGUAGES } from '../i18n'
import { Button } from './ui'

export function LanguageSelect() {
  const { t, i18n } = useTranslation()
  return (
    <select
      aria-label={t('app.language')}
      value={i18n.language}
      onChange={(e) => void i18n.changeLanguage(e.target.value)}
      className="rounded-md border border-stone-300 bg-transparent px-2 py-1 text-sm dark:border-stone-700"
    >
      {Object.entries(LANGUAGES).map(([code, label]) => (
        <option key={code} value={code}>
          {label}
        </option>
      ))}
    </select>
  )
}

export function Footer() {
  const { t } = useTranslation()
  return <footer className="py-6 text-center text-xs text-stone-500">{t('footer.vibecoded')}</footer>
}

export function Layout() {
  const { t } = useTranslation()
  const { data: me } = useMe()
  const logout = useLogout()
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-stone-200 bg-white dark:border-stone-800 dark:bg-stone-900">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-3">
          <Link to="/" className="text-lg font-semibold text-brand-700 dark:text-brand-100">
            {t('app.name')}
          </Link>
          <div className="flex items-center gap-3 text-sm">
            {me?.is_admin && (
              <Link to="/ia" className="text-stone-600 hover:text-stone-900 dark:text-stone-300">
                {t('app.ai_settings')}
              </Link>
            )}
            <Link to="/conta" className="hidden text-stone-500 hover:underline sm:inline">
              {me?.full_name}
            </Link>
            <LanguageSelect />
            <Button variant="ghost" onClick={() => logout.mutate()}>
              {t('app.logout')}
            </Button>
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8">
        <Outlet />
      </main>
      <Footer />
    </div>
  )
}
