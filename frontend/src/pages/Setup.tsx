import { useState, type FormEvent } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '../api/client'
import type { User } from '../api/types'
import { Brand, Button, Card, CenteredPage, ErrorText, Field, Input } from '../components/ui'

export default function Setup() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [form, setForm] = useState({ email: '', full_name: '', password: '' })
  const setup = useMutation({
    mutationFn: () => api.post<User>('/setup', form),
    onSuccess: (user) => {
      qc.setQueryData(['setup'], { needs_setup: false })
      qc.setQueryData(['me'], user)
    },
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    setup.mutate()
  }
  return (
    <CenteredPage>
      <Brand />
      <Card>
        <form onSubmit={submit} className="space-y-4">
          <div>
            <h2 className="text-lg font-semibold">{t('setup.title')}</h2>
            <p className="text-sm text-stone-500">{t('setup.intro')}</p>
          </div>
          <Field label={t('fields.full_name')}>
            <Input
              required
              autoComplete="name"
              value={form.full_name}
              onChange={(e) => setForm({ ...form, full_name: e.target.value })}
            />
          </Field>
          <Field label={t('fields.email')}>
            <Input
              required
              type="email"
              autoComplete="email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
            />
          </Field>
          <Field label={t('fields.password')} hint={t('fields.password_hint')}>
            <Input
              required
              type="password"
              minLength={10}
              autoComplete="new-password"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
            />
          </Field>
          <ErrorText error={setup.error} />
          <Button type="submit" className="w-full" disabled={setup.isPending}>
            {t('setup.submit')}
          </Button>
        </form>
      </Card>
    </CenteredPage>
  )
}
