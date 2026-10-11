import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api/client'
import { useMe } from '../api/hooks'
import type { InvitationInfo, User } from '../api/types'
import { Brand, Button, Card, CenteredPage, ErrorText, Field, Input } from '../components/ui'

export default function AcceptInvite() {
  const { token = '' } = useParams()
  const { t } = useTranslation()
  const qc = useQueryClient()
  const navigate = useNavigate()
  const { data: me } = useMe()
  const info = useQuery({
    queryKey: ['invitation', token],
    queryFn: () => api.get<InvitationInfo>(`/invitations/${token}`),
    retry: false,
  })
  const [form, setForm] = useState({ full_name: '', password: '' })
  const accept = useMutation({
    mutationFn: () =>
      api.post<User>(`/invitations/${token}/accept`, info.data?.account_exists ? {} : form),
    onSuccess: (user) => {
      qc.setQueryData(['me'], user)
      void qc.invalidateQueries({ queryKey: ['projects'] })
      navigate('/', { replace: true })
    },
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    accept.mutate()
  }

  let body
  if (info.isLoading) body = <p className="text-stone-500">{t('app.loading')}</p>
  else if (!info.data) body = <p>{t('invite.invalid')}</p>
  else {
    const inv = info.data
    const loggedAsInvitee = me?.email === inv.email
    body = (
      <form onSubmit={submit} className="space-y-4">
        <h2 className="text-lg font-semibold">{t('invite.title')}</h2>
        <p className="text-sm">
          {inv.project_title
            ? t('invite.for_project', {
                project: inv.project_title,
                role: t(`role.${inv.role ?? 'reviewer'}`),
              })
            : t('invite.for_instance')}
        </p>
        {inv.account_exists && !loggedAsInvitee ? (
          <p className="text-sm">
            {t('invite.login_first', { email: inv.email })}{' '}
            <Link
              to="/login"
              state={{ from: `/convite/${token}` }}
              className="text-brand-600 underline"
            >
              {t('login.submit')}
            </Link>
          </p>
        ) : inv.account_exists ? (
          <Button type="submit" className="w-full" disabled={accept.isPending}>
            {t('invite.accept')}
          </Button>
        ) : (
          <>
            <p className="text-sm text-stone-500">{t('invite.create_account')}</p>
            <Field label={t('fields.email')}>
              <Input value={inv.email} readOnly disabled />
            </Field>
            <Field label={t('fields.full_name')}>
              <Input
                required
                autoComplete="name"
                value={form.full_name}
                onChange={(e) => setForm({ ...form, full_name: e.target.value })}
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
            <Button type="submit" className="w-full" disabled={accept.isPending}>
              {t('invite.accept')}
            </Button>
          </>
        )}
        <ErrorText error={accept.error} />
      </form>
    )
  }

  return (
    <CenteredPage>
      <Brand />
      <Card>{body}</Card>
    </CenteredPage>
  )
}
