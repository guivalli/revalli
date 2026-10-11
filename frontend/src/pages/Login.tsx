import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { useLocation, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import type { User } from '../api/types'
import { Footer, LanguageSelect } from '../components/Layout'
import { Brand, Button, Card, CenteredPage, ErrorText, Field, Input } from '../components/ui'

export default function Login() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const navigate = useNavigate()
  const location = useLocation()
  const [form, setForm] = useState({ email: '', password: '' })
  const login = useMutation({
    mutationFn: () => api.post<User>('/auth/login', form),
    onSuccess: (user) => {
      qc.setQueryData(['me'], user)
      const next = (location.state as { from?: string } | null)?.from ?? '/'
      navigate(next, { replace: true })
    },
  })
  const oidc = useQuery({
    queryKey: ['oidc'],
    queryFn: () => api.get<{ enabled: boolean; label: string }>('/auth/oidc/config'),
    staleTime: 60_000,
  })
  const oidcError = new URLSearchParams(location.search).get('erro')
  const submit = (e: FormEvent) => {
    e.preventDefault()
    login.mutate()
  }
  return (
    <CenteredPage>
      <Brand />
      <Card>
        <form onSubmit={submit} className="space-y-4">
          <h2 className="text-lg font-semibold">{t('login.title')}</h2>
          <Field label={t('fields.email')}>
            <Input
              required
              type="email"
              autoComplete="email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
            />
          </Field>
          <Field label={t('fields.password')}>
            <Input
              required
              type="password"
              autoComplete="current-password"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
            />
          </Field>
          <ErrorText error={login.error} />
          {oidcError && (
            <p role="alert" className="text-sm text-red-700 dark:text-red-400">
              {t(`login.oidc_${oidcError}`, { defaultValue: t('login.oidc_failed') })}
            </p>
          )}
          <Button type="submit" className="w-full" disabled={login.isPending}>
            {t('login.submit')}
          </Button>
        </form>
        {oidc.data?.enabled && (
          <div className="mt-4 border-t border-stone-200 pt-4 dark:border-stone-800">
            {/* Navegação de página inteira: o provedor devolve a pessoa por redirecionamento */}
            <a
              href="/api/auth/oidc/login"
              className="inline-flex w-full items-center justify-center rounded-md border border-stone-300 px-3 py-2 text-sm font-medium hover:bg-stone-100 dark:border-stone-700 dark:hover:bg-stone-800"
            >
              {oidc.data.label || t('login.sso')}
            </a>
          </div>
        )}
      </Card>
      <div className="flex justify-center">
        <LanguageSelect />
      </div>
      <Footer />
    </CenteredPage>
  )
}
