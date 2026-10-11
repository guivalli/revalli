import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { useCreateProject, useProjects } from '../api/hooks'
import { REVIEW_TYPES, type ReviewType } from '../api/types'
import { Button, Card, ErrorText, Field, Input, Select } from '../components/ui'

function NewProjectForm({ onDone }: { onDone: () => void }) {
  const { t } = useTranslation()
  const create = useCreateProject()
  const [form, setForm] = useState({
    title: '',
    description: '',
    review_type: 'systematic' as ReviewType,
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    create.mutate(form, { onSuccess: onDone })
  }
  return (
    <Card>
      <form onSubmit={submit} className="space-y-4">
        <Field label={t('fields.title')}>
          <Input
            required
            autoFocus
            maxLength={500}
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
          />
        </Field>
        <Field label={t('fields.review_type')}>
          <Select
            value={form.review_type}
            onChange={(e) => setForm({ ...form, review_type: e.target.value as ReviewType })}
          >
            {REVIEW_TYPES.map((rt) => (
              <option key={rt} value={rt}>
                {t(`review_type.${rt}`)}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={t('fields.description')}>
          <textarea
            rows={3}
            className="w-full rounded-md border border-stone-300 bg-white px-3 py-2 text-sm dark:border-stone-700 dark:bg-stone-900"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
          />
        </Field>
        <ErrorText error={create.error} />
        <div className="flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onDone}>
            {t('projects.cancel')}
          </Button>
          <Button type="submit" disabled={create.isPending}>
            {t('projects.create')}
          </Button>
        </div>
      </form>
    </Card>
  )
}

export default function Projects() {
  const { t } = useTranslation()
  const { data, isLoading, error } = useProjects()
  const [creating, setCreating] = useState(false)
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{t('projects.title')}</h1>
        {!creating && <Button onClick={() => setCreating(true)}>{t('projects.new')}</Button>}
      </div>
      {creating && <NewProjectForm onDone={() => setCreating(false)} />}
      <ErrorText error={error} />
      {isLoading && <p className="text-stone-500">{t('app.loading')}</p>}
      {data && data.length === 0 && !creating && (
        <p className="text-stone-500">{t('projects.empty')}</p>
      )}
      <ul className="grid gap-4 sm:grid-cols-2">
        {data?.map((p) => (
          <li key={p.id}>
            <Link
              to={`/projetos/${p.id}`}
              className="block rounded-lg border border-stone-200 bg-white p-5 shadow-sm transition hover:border-brand-500 dark:border-stone-800 dark:bg-stone-900"
            >
              <h2 className="font-semibold">{p.title}</h2>
              <p className="mt-1 text-sm text-stone-500">
                {t(`review_type.${p.review_type}`)} ·{' '}
                {t('projects.members_count', { count: p.member_count })}
                {p.my_role && <> · {t(`role.${p.my_role}`)}</>}
              </p>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}
