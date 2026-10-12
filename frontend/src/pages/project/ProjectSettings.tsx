import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { useDeleteProject, useUpdateProject } from '../../api/hooks'
import { useSummary } from '../../api/records'
import { REVIEW_TYPES, type ReviewType } from '../../api/types'
import { Button, Card, ErrorText, Field, Input, Select } from '../../components/ui'
import { useProjectContext } from './context'

function EditCard() {
  const { t } = useTranslation()
  const { project } = useProjectContext()
  const update = useUpdateProject(project.id)
  const [form, setForm] = useState({
    title: project.title,
    description: project.description,
    review_type: project.review_type as ReviewType,
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    update.mutate(form)
  }
  return (
    <Card>
      <form onSubmit={submit} className="space-y-4">
        <h2 className="font-semibold">{t('project_settings.edit_title')}</h2>
        <Field label={t('fields.title')}>
          <Input
            required
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
            rows={4}
            className="w-full rounded-md border border-stone-300 bg-white px-3 py-2 text-sm dark:border-stone-700 dark:bg-stone-900"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
          />
        </Field>
        <ErrorText error={update.error} />
        {update.isSuccess && (
          <p role="status" className="text-sm text-brand-700 dark:text-brand-100">
            {t('project_settings.saved')}
          </p>
        )}
        <Button type="submit" disabled={update.isPending || !form.title.trim()}>
          {t('project_settings.save')}
        </Button>
      </form>
    </Card>
  )
}

function DangerCard() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { project } = useProjectContext()
  const { data: summary } = useSummary(project.id)
  const del = useDeleteProject(project.id)
  const [open, setOpen] = useState(false)
  const [typed, setTyped] = useState('')
  const matches = typed.trim() === project.title.trim()
  return (
    <Card className="space-y-3 border-red-200 dark:border-red-900">
      <h2 className="font-semibold text-red-700 dark:text-red-400">{t('project_settings.danger')}</h2>
      <p className="text-sm text-stone-600 dark:text-stone-400">
        {t('project_settings.delete_hint', { count: summary?.records_total ?? 0 })}
      </p>
      {!open ? (
        <Button variant="danger" onClick={() => setOpen(true)}>
          {t('project_settings.delete')}
        </Button>
      ) : (
        <div className="space-y-3">
          <Field label={t('project_settings.type_title', { title: project.title })}>
            <Input value={typed} autoFocus onChange={(e) => setTyped(e.target.value)} />
          </Field>
          <ErrorText error={del.error} />
          <div className="flex gap-2">
            <Button
              variant="ghost"
              onClick={() => {
                setOpen(false)
                setTyped('')
              }}
            >
              {t('projects.cancel')}
            </Button>
            <Button
              variant="danger"
              disabled={!matches || del.isPending}
              onClick={() => del.mutate(undefined, { onSuccess: () => navigate('/', { replace: true }) })}
            >
              {t('project_settings.delete_confirm')}
            </Button>
          </div>
        </div>
      )}
    </Card>
  )
}

export default function ProjectSettings() {
  const { t } = useTranslation()
  const { canManage } = useProjectContext()
  if (!canManage) return <p className="text-stone-500">{t('protocol.readonly')}</p>
  return (
    <div className="space-y-6">
      <EditCard />
      <DangerCard />
    </div>
  )
}
