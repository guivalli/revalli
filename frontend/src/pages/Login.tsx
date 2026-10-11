import { useState, type FormEvent } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
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
          <Button type="submit" className="w-full" disabled={login.isPending}>
            {t('login.submit')}
          </Button>
        </form>
      </Card>
      <div className="flex justify-center">
        <LanguageSelect />
      </div>
      <Footer />
    </CenteredPage>
  )
}
