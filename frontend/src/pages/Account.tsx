import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useChangePassword, useProjects } from '../api/hooks'
import { useApiTokenActions, useApiTokens } from '../api/tokens'
import { Button, Card, ErrorText, Field, Input, Select } from '../components/ui'

function ChangePassword() {
  const { t } = useTranslation()
  const change = useChangePassword()
  const [form, setForm] = useState({ current: '', next: '', again: '' })
  const mismatch = form.again.length > 0 && form.again !== form.next
  return (
    <Card className="space-y-4">
      <h2 className="font-semibold">{t('account.password_title')}</h2>
      <form
        className="grid gap-4 sm:grid-cols-3"
        onSubmit={(e) => {
          e.preventDefault()
          if (mismatch) return
          change.mutate(
            { current_password: form.current, new_password: form.next },
            { onSuccess: () => setForm({ current: '', next: '', again: '' }) },
          )
        }}
      >
        <Field label={t('account.password_current')}>
          <Input
            required
            type="password"
            autoComplete="current-password"
            value={form.current}
            onChange={(e) => setForm({ ...form, current: e.target.value })}
          />
        </Field>
        <Field label={t('account.password_new')} hint={t('reset.password_hint', { min: 10 })}>
          <Input
            required
            type="password"
            autoComplete="new-password"
            minLength={10}
            value={form.next}
            onChange={(e) => setForm({ ...form, next: e.target.value })}
          />
        </Field>
        <Field label={t('reset.repeat')}>
          <Input
            required
            type="password"
            autoComplete="new-password"
            value={form.again}
            onChange={(e) => setForm({ ...form, again: e.target.value })}
          />
        </Field>
        <div className="space-y-2 sm:col-span-3">
          {mismatch && <p className="text-sm text-red-700 dark:text-red-400">{t('reset.mismatch')}</p>}
          <ErrorText error={change.error} />
          {change.isSuccess && (
            <p role="status" className="text-sm text-brand-700 dark:text-brand-100">
              {t('account.password_saved')}
            </p>
          )}
          <Button type="submit" disabled={change.isPending || mismatch}>
            {t('account.password_save')}
          </Button>
        </div>
      </form>
    </Card>
  )
}

export default function Account() {
  const { t, i18n } = useTranslation()
  const tokens = useApiTokens()
  const projects = useProjects()
  const { create, revoke } = useApiTokenActions()
  const [name, setName] = useState('')
  const [projectId, setProjectId] = useState('')
  const [days, setDays] = useState('')
  const fmt = (iso: string | null) => (iso ? new Date(iso).toLocaleString(i18n.language) : '–')
  const projectName = (id: string | null) =>
    id ? (projects.data?.find((p) => p.id === id)?.title ?? id) : t('account.all_projects')

  return (
    <div className="space-y-6">
      <ChangePassword />
      <Card className="space-y-4">
        <div>
          <h2 className="font-semibold">{t('account.tokens_title')}</h2>
          <p className="text-sm text-stone-500">{t('account.tokens_hint')}</p>
        </div>
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label={t('account.token_name')}>
            <Input value={name} maxLength={100} onChange={(e) => setName(e.target.value)} />
          </Field>
          <Field label={t('account.token_project')}>
            <Select value={projectId} onChange={(e) => setProjectId(e.target.value)}>
              <option value="">{t('account.all_projects')}</option>
              {(projects.data ?? []).map((p) => (
                <option key={p.id} value={p.id}>
                  {p.title}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t('account.token_days')} hint={t('account.token_days_hint')}>
            <Input
              type="number"
              min={1}
              max={3650}
              value={days}
              onChange={(e) => setDays(e.target.value)}
            />
          </Field>
        </div>
        <Button
          disabled={!name.trim() || create.isPending}
          onClick={() =>
            create.mutate(
              {
                name: name.trim(),
                project_id: projectId || null,
                expires_in_days: days ? Number(days) : null,
              },
              {
                onSuccess: () => {
                  setName('')
                  setDays('')
                },
              },
            )
          }
        >
          {t('account.create_token')}
        </Button>
        <ErrorText error={create.error ?? revoke.error} />
        {create.data && (
          <div role="status" className="space-y-1 rounded-md bg-emerald-50 p-3 text-sm dark:bg-emerald-950">
            <p className="font-medium">{t('account.token_once')}</p>
            <code className="block break-all rounded bg-white p-2 font-mono text-xs dark:bg-stone-900">
              {create.data.token}
            </code>
          </div>
        )}
      </Card>

      <Card className="space-y-3">
        <h3 className="font-semibold">{t('account.your_tokens')}</h3>
        {(tokens.data ?? []).length === 0 && (
          <p className="text-sm text-stone-500">{t('account.no_tokens')}</p>
        )}
        <ul className="divide-y divide-stone-200 dark:divide-stone-800">
          {(tokens.data ?? []).map((tk) => (
            <li key={tk.id} className="flex flex-wrap items-center justify-between gap-3 py-3 text-sm">
              <div>
                <p className="font-medium">
                  {tk.name} <span className="font-mono text-xs text-stone-500">{tk.prefix}…</span>
                </p>
                <p className="text-xs text-stone-500">
                  {projectName(tk.project_id)} · {t('account.created', { date: fmt(tk.created_at) })} ·{' '}
                  {t('account.last_used', { date: fmt(tk.last_used_at) })}
                  {tk.expires_at && ` · ${t('account.expires', { date: fmt(tk.expires_at) })}`}
                </p>
              </div>
              <Button variant="danger" onClick={() => revoke.mutate(tk.id)}>
                {t('account.revoke')}
              </Button>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  )
}
