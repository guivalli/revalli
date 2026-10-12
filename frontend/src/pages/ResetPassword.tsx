import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api/client'
import type { User } from '../api/types'
import { Brand, Button, Card, CenteredPage, ErrorText, Field, Input } from '../components/ui'

const MIN = 10

/** Página aberta pelo link de nova senha que o administrador gerou. */
export default function ResetPassword() {
  const { token = '' } = useParams()
  const { t } = useTranslation()
  const qc = useQueryClient()
  const navigate = useNavigate()
  const info = useQuery({
    queryKey: ['password-reset', token],
    queryFn: () => api.get<{ email: string; full_name: string }>(`/password-resets/${token}`),
    retry: false,
  })
  const [password, setPassword] = useState('')
  const [again, setAgain] = useState('')
  const accept = useMutation({
    mutationFn: () => api.post<User>(`/password-resets/${token}/accept`, { password }),
    onSuccess: (user) => {
      qc.setQueryData(['me'], user)
      void qc.invalidateQueries()
      navigate('/', { replace: true })
    },
  })
  const mismatch = again.length > 0 && again !== password
  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (!mismatch) accept.mutate()
  }

  let body
  if (info.isLoading) body = <p className="text-stone-500">{t('app.loading')}</p>
  else if (!info.data) body = <p>{t('reset.invalid')}</p>
  else
    body = (
      <form onSubmit={submit} className="space-y-4">
        <h2 className="text-lg font-semibold">{t('reset.title')}</h2>
        <p className="text-sm text-stone-600 dark:text-stone-400">
          {t('reset.for', { name: info.data.full_name, email: info.data.email })}
        </p>
        <Field label={t('reset.new_password')} hint={t('reset.password_hint', { min: MIN })}>
          <Input
            required
            autoFocus
            type="password"
            autoComplete="new-password"
            minLength={MIN}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </Field>
        <Field label={t('reset.repeat')}>
          <Input
            required
            type="password"
            autoComplete="new-password"
            value={again}
            onChange={(e) => setAgain(e.target.value)}
          />
        </Field>
        {mismatch && <p className="text-sm text-red-700 dark:text-red-400">{t('reset.mismatch')}</p>}
        <ErrorText error={accept.error} />
        <Button type="submit" className="w-full" disabled={accept.isPending || mismatch || password.length < MIN}>
          {t('reset.submit')}
        </Button>
      </form>
    )

  return (
    <CenteredPage>
      <Brand />
      <Card>{body}</Card>
    </CenteredPage>
  )
}
