import type { ButtonHTMLAttributes, ComponentProps, ReactNode, SelectHTMLAttributes } from 'react'
import { useTranslation } from 'react-i18next'
import { ApiError } from '../api/client'
import { Logo } from './Logo'

const cx = (...c: (string | false | undefined)[]) => c.filter(Boolean).join(' ')

export function Button({
  variant = 'primary',
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'ghost' | 'danger' }) {
  return (
    <button
      {...props}
      className={cx(
        'inline-flex items-center justify-center rounded-md px-3 py-2 text-sm font-medium transition disabled:opacity-50',
        variant === 'primary' && 'bg-brand-600 text-white hover:bg-brand-700',
        variant === 'ghost' &&
          'text-stone-700 hover:bg-stone-200 dark:text-stone-300 dark:hover:bg-stone-800',
        variant === 'danger' &&
          'text-red-700 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-950',
        className,
      )}
    />
  )
}

const fieldClass =
  'w-full rounded-md border border-stone-300 bg-white px-3 py-2 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100 dark:border-stone-700 dark:bg-stone-900 dark:focus:ring-brand-700'

export function Input(props: ComponentProps<'input'>) {
  return <input {...props} className={cx(fieldClass, props.className)} />
}

export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={cx(fieldClass, props.className)} />
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="block space-y-1">
      <span className="text-sm font-medium">{label}</span>
      {children}
      {hint && <span className="block text-xs text-stone-500">{hint}</span>}
    </label>
  )
}

export function Card({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={cx(
        'rounded-lg border border-stone-200 bg-white p-6 shadow-sm dark:border-stone-800 dark:bg-stone-900',
        className,
      )}
    >
      {children}
    </div>
  )
}

/** Cartão com cabeçalho: título à esquerda e ações à direita, separados do conteúdo. */
export function Section({
  title,
  actions,
  children,
  className,
}: {
  title: ReactNode
  actions?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <section
      className={cx(
        'overflow-hidden rounded-lg border border-stone-200 bg-white shadow-sm dark:border-stone-800 dark:bg-stone-900',
        className,
      )}
    >
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-stone-200 px-5 py-3 dark:border-stone-800">
        <h2 className="font-semibold">{title}</h2>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </header>
      <div className="p-5">{children}</div>
    </section>
  )
}

export function ErrorText({ error }: { error: unknown }) {
  const { t } = useTranslation()
  if (!error) return null
  // O servidor pode mandar "codigo: detalhe"; o detalhe aparece depois da mensagem traduzida
  const [code, detail] = (error instanceof ApiError ? error.code : 'unknown_error').split(/: (.*)/s)
  const msg = t(`errors.${code}`, { defaultValue: t('errors.unknown_error') })
  return (
    <p role="alert" className="text-sm text-red-700 dark:text-red-400">
      {msg}
      {detail && <span className="block text-xs opacity-80">{detail}</span>}
    </p>
  )
}

export function CenteredPage({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-10">
      <div className="w-full max-w-md space-y-6">{children}</div>
    </div>
  )
}

export function Brand() {
  const { t } = useTranslation()
  return (
    <div className="flex flex-col items-center gap-2 text-center">
      <Logo variant="stacked" height={132} />
      <p className="text-sm text-stone-500">{t('app.tagline')}</p>
    </div>
  )
}
