import { useState, type ReactNode } from 'react'
import { Link, Outlet } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useLogout, useMe } from '../api/hooks'
import { LANGUAGES } from '../i18n'
import { useTheme, type ThemeChoice } from '../lib/theme'
import { AppMenu } from './AppMenu'
import { Logo } from './Logo'
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

const THEMES: { value: ThemeChoice; icon: ReactNode }[] = [
  {
    value: 'light',
    icon: (
      <svg viewBox="0 0 24 24" className="size-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
        <circle cx="12" cy="12" r="4" />
        <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
      </svg>
    ),
  },
  {
    value: 'system',
    icon: (
      <svg viewBox="0 0 24 24" className="size-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
        <rect x="3" y="4" width="18" height="12" rx="2" />
        <path d="M8 20h8M12 16v4" />
      </svg>
    ),
  },
  {
    value: 'dark',
    icon: (
      <svg viewBox="0 0 24 24" className="size-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
      </svg>
    ),
  },
]

/** Alterna entre claro, automático (segue o sistema) e escuro. */
export function ThemeSwitch() {
  const { t } = useTranslation()
  const [theme, setTheme] = useTheme()
  return (
    <div
      role="radiogroup"
      aria-label={t('app.theme')}
      className="flex rounded-md border border-stone-300 p-0.5 dark:border-stone-700"
    >
      {THEMES.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={theme === o.value}
          aria-label={t(`app.theme_${o.value}`)}
          title={t(`app.theme_${o.value}`)}
          onClick={() => setTheme(o.value)}
          className={`rounded px-2 py-1 transition ${
            theme === o.value
              ? 'bg-brand-600 text-white'
              : 'text-stone-600 hover:bg-stone-100 dark:text-stone-300 dark:hover:bg-stone-800'
          }`}
        >
          <span aria-hidden className="block">{o.icon}</span>
        </button>
      ))}
    </div>
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
  const [menu, setMenu] = useState(false)
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-stone-200 bg-white dark:border-stone-800 dark:bg-stone-900">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setMenu(true)}
              aria-label={t('app.menu')}
              aria-expanded={menu}
              className="rounded-md p-2 text-stone-600 hover:bg-stone-100 dark:text-stone-300 dark:hover:bg-stone-800"
            >
              <svg aria-hidden viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <path d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
            <Link to="/" aria-label={t('menu.all_reviews')} title={t('menu.all_reviews')} className="flex items-center">
              <Logo variant="icon" height={36} className="sm:hidden" />
              <Logo variant="wordmark" height={36} className="hidden sm:block" />
            </Link>
          </div>
          <div className="flex items-center gap-3 text-sm">
            {me?.is_admin && (
              <Link to="/ia" className="text-stone-600 hover:text-stone-900 dark:text-stone-300">
                {t('app.ai_settings')}
              </Link>
            )}
            <Link to="/conta" className="hidden text-stone-500 hover:underline sm:inline">
              {me?.full_name}
            </Link>
            <ThemeSwitch />
            <LanguageSelect />
            <Button variant="ghost" onClick={() => logout.mutate()}>
              {t('app.logout')}
            </Button>
          </div>
        </div>
      </header>
      <AppMenu open={menu} onClose={() => setMenu(false)} />
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-8">
        <Outlet />
      </main>
      <Footer />
    </div>
  )
}
