import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useCreatePasswordReset, useMe, useMemberActions, useMembers } from '../../api/hooks'
import { ROLES, type Role } from '../../api/types'
import { Button, Card, ErrorText, Field, Input, Select } from '../../components/ui'
import { useProjectContext } from './context'

function InviteForm({ projectId }: { projectId: string }) {
  const { t } = useTranslation()
  const { invite } = useMemberActions(projectId)
  const [email, setEmail] = useState('')
  const [role, setRole] = useState<Role>('reviewer')
  const [copied, setCopied] = useState(false)
  const submit = (e: FormEvent) => {
    e.preventDefault()
    setCopied(false)
    invite.mutate({ email, role })
  }
  const copy = async (url: string) => {
    try {
      await navigator.clipboard.writeText(url)
      setCopied(true)
    } catch {
      /* área de transferência indisponível */
    }
  }
  return (
    <Card className="space-y-4">
      <h2 className="font-semibold">{t('members.invite_title')}</h2>
      <form onSubmit={submit} className="grid gap-3 sm:grid-cols-[1fr_12rem_auto] sm:items-end">
        <Field label={t('fields.email')}>
          <Input required type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </Field>
        <Field label={t('fields.role')}>
          <Select value={role} onChange={(e) => setRole(e.target.value as Role)}>
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {t(`role.${r}`)}
              </option>
            ))}
          </Select>
        </Field>
        <Button type="submit" disabled={invite.isPending}>
          {t('members.invite_submit')}
        </Button>
      </form>
      <ErrorText error={invite.error} />
      {invite.data && (
        <div className="space-y-2 rounded-md bg-brand-50 p-3 text-sm dark:bg-stone-800">
          <p>{t('members.invite_ready', { email: invite.data.email })}</p>
          <div className="flex gap-2">
            <Input readOnly value={invite.data.invite_url} onFocus={(e) => e.target.select()} />
            <Button type="button" variant="ghost" onClick={() => copy(invite.data.invite_url)}>
              {copied ? t('members.copied') : t('members.copy')}
            </Button>
          </div>
        </div>
      )}
    </Card>
  )
}

export default function Members() {
  const { t } = useTranslation()
  const { project, canManage } = useProjectContext()
  const members = useMembers(project.id)
  const { changeRole, remove } = useMemberActions(project.id)
  const { data: me } = useMe()
  const reset = useCreatePasswordReset()
  const [resetFor, setResetFor] = useState<string | null>(null)

  return (
    <div className="space-y-6">
      <Card className="space-y-3">
        <h2 className="font-semibold">{t('members.title')}</h2>
        <ErrorText error={changeRole.error ?? remove.error ?? reset.error} />
        {reset.data && resetFor && (
          <div className="space-y-2 rounded-md border border-brand-200 bg-brand-50 p-3 text-sm dark:border-brand-800 dark:bg-brand-900/30">
            <p>{t('members.reset_ready', { email: reset.data.email })}</p>
            <Input readOnly value={reset.data.reset_url} onFocus={(e) => e.target.select()} />
            <p className="text-xs text-stone-500">{t('members.reset_hint')}</p>
          </div>
        )}
        <ul className="divide-y divide-stone-200 dark:divide-stone-800">
          {members.data?.map((m) => (
            <li key={m.user_id} className="flex flex-wrap items-center justify-between gap-2 py-3">
              <div>
                <p className="font-medium">{m.full_name}</p>
                <p className="text-sm text-stone-500">{m.email}</p>
              </div>
              {canManage ? (
                <div className="flex items-center gap-2">
                  <Select
                    aria-label={t('fields.role')}
                    className="w-40"
                    value={m.role}
                    onChange={(e) =>
                      changeRole.mutate({ userId: m.user_id, role: e.target.value as Role })
                    }
                  >
                    {ROLES.map((r) => (
                      <option key={r} value={r}>
                        {t(`role.${r}`)}
                      </option>
                    ))}
                  </Select>
                  {me?.is_admin && m.user_id !== me.id && (
                    <Button
                      variant="ghost"
                      onClick={() => {
                        setResetFor(m.user_id)
                        reset.mutate(m.user_id)
                      }}
                      disabled={reset.isPending}
                    >
                      {t('members.reset_link')}
                    </Button>
                  )}
                  <Button variant="danger" onClick={() => remove.mutate(m.user_id)}>
                    {t('members.remove')}
                  </Button>
                </div>
              ) : (
                <span className="text-sm">{t(`role.${m.role}`)}</span>
              )}
            </li>
          ))}
        </ul>
      </Card>
      {canManage && <InviteForm projectId={project.id} />}
    </div>
  )
}
