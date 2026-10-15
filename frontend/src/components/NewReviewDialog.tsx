import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { useInstanceAI } from '../api/ai'
import { api } from '../api/client'
import {
  REVIEW_TYPES,
  ROLES,
  type InvitationCreated,
  type Project,
  type ProjectAISettings,
  type ReviewType,
  type Role,
  type ScreeningSettings,
} from '../api/types'
import { Button, ErrorText, Field, Input, Select } from './ui'

type Step = 1 | 2 | 3 | 4 | 'done'
type Invite = { email: string; role: Role }

const MAX_INVITES = 8

function Stepper({ step }: { step: Step }) {
  const { t } = useTranslation()
  const current = step === 'done' ? 5 : step
  const labels = [t('wizard.step_info'), t('wizard.step_references'), t('wizard.step_team'), t('wizard.step_ai')]
  return (
    <ol className="grid grid-cols-4 border-b border-stone-200 dark:border-stone-800">
      {labels.map((label, i) => {
        const n = i + 1
        const active = current === n
        const done = current > n
        return (
          <li
            key={label}
            aria-current={active ? 'step' : undefined}
            className={`flex items-center justify-center gap-2 border-b-2 px-2 py-3 text-sm ${
              active
                ? 'border-brand-600 font-medium text-brand-700 dark:text-brand-100'
                : 'border-transparent text-stone-500'
            }`}
          >
            <span
              className={`flex size-6 items-center justify-center rounded-full text-xs ${
                active || done
                  ? 'bg-brand-600 text-white'
                  : 'border border-stone-300 dark:border-stone-600'
              }`}
            >
              {done ? '✓' : n}
            </span>
            <span className="hidden sm:inline">{label}</span>
          </li>
        )
      })}
    </ol>
  )
}

function Choice({
  checked,
  onChange,
  title,
  hint,
  disabled = false,
}: {
  checked: boolean
  onChange: () => void
  title: string
  hint: string
  disabled?: boolean
}) {
  return (
    <label
      className={`flex items-start gap-3 rounded-lg border p-4 transition ${
        disabled ? 'cursor-not-allowed opacity-60' : 'cursor-pointer'
      } ${
        checked
          ? 'border-brand-500 bg-brand-50 dark:border-brand-500 dark:bg-brand-900/20'
          : 'border-stone-200 hover:border-stone-400 dark:border-stone-700'
      }`}
    >
      <input
        type="radio"
        className="mt-1 accent-brand-600"
        checked={checked}
        disabled={disabled}
        onChange={onChange}
      />
      <span>
        <span className="block text-sm font-medium">{title}</span>
        <span className="block text-xs text-stone-500">{hint}</span>
      </span>
    </label>
  )
}

/** Assistente de nova revisão: informações, referências, equipe e IA. Ao terminar, mostra os
 * convites criados e abre a revisão onde o próximo passo é mais útil. */
export function NewReviewDialog({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [step, setStep] = useState<Step>(1)
  const [form, setForm] = useState({ title: '', description: '', review_type: 'systematic' as ReviewType })
  const [references, setReferences] = useState<'import' | 'later'>('import')
  const [team, setTeam] = useState<'alone' | 'invite'>('alone')
  const [invites, setInvites] = useState<Invite[]>([{ email: '', role: 'reviewer' }])
  const [ai, setAi] = useState<'on' | 'off'>('off')
  const instance = useInstanceAI()
  const aiAvailable = !!instance.data?.screening.provider_id && !!instance.data?.screening.model
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const [created, setCreated] = useState<{ project: Project; links: InvitationCreated[] } | null>(null)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && step !== 'done' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose, step])

  const finish = async () => {
    setBusy(true)
    setError(null)
    try {
      const project = await api.post<Project>('/projects', {
        title: form.title.trim(),
        description: form.description,
        review_type: form.review_type,
      })
      const links: InvitationCreated[] = []
      if (team === 'alone') {
        // Sozinho, uma decisão basta; senão a fase de texto completo nunca recebe registros
        const current = await api.get<ScreeningSettings>(`/projects/${project.id}/screening/settings`)
        await api.put(`/projects/${project.id}/screening/settings`, {
          ...current,
          reviewers_title_abstract: 1,
          reviewers_full_text: 1,
        })
      } else {
        for (const invite of invites.filter((i) => i.email.trim())) {
          links.push(
            await api.post<InvitationCreated>('/invitations', {
              email: invite.email.trim(),
              role: invite.role,
              project_id: project.id,
            }),
          )
        }
      }
      if (ai === 'on' && aiAvailable) {
        const current = await api.get<ProjectAISettings>(`/projects/${project.id}/ai/settings`)
        await api.put(`/projects/${project.id}/ai/settings`, { ...current, enabled: true })
      }
      void qc.invalidateQueries({ queryKey: ['projects'] })
      setCreated({ project, links })
      setStep('done')
    } catch (e) {
      setError(e)
    } finally {
      setBusy(false)
    }
  }

  const next = (e: FormEvent) => {
    e.preventDefault()
    if (step === 1) setStep(2)
    else if (step === 2) setStep(3)
    else if (step === 3) setStep(4)
    else if (step === 4) void finish()
  }

  const open = () => {
    if (!created) return
    onClose()
    navigate(`/projetos/${created.project.id}${references === 'import' ? '/importar' : ''}`)
  }

  const setInvite = (i: number, patch: Partial<Invite>) =>
    setInvites(invites.map((inv, j) => (j === i ? { ...inv, ...patch } : inv)))

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-stone-900/50 px-4 py-10"
      onMouseDown={(e) => e.target === e.currentTarget && step !== 'done' && onClose()}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="new-review-title"
        className="w-full max-w-2xl rounded-xl border border-stone-200 bg-white shadow-xl dark:border-stone-800 dark:bg-stone-900"
      >
        <div className="flex items-center justify-between px-6 pt-5">
          <h2 id="new-review-title" className="text-lg font-semibold">
            {t('wizard.title')}
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label={t('projects.cancel')}
            className="rounded p-1 text-stone-500 hover:bg-stone-100 dark:hover:bg-stone-800"
          >
            ✕
          </button>
        </div>
        <div className="mt-4">
          <Stepper step={step} />
        </div>

        {step !== 'done' && (
          <form onSubmit={next} className="space-y-5 px-6 py-6">
            {step === 1 && (
              <>
                <Field label={`${t('fields.title')} *`}>
                  <Input
                    required
                    autoFocus
                    maxLength={500}
                    placeholder={t('wizard.title_placeholder')}
                    value={form.title}
                    onChange={(e) => setForm({ ...form, title: e.target.value })}
                  />
                </Field>
                <Field label={`${t('fields.review_type')} *`}>
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
                <Field label={t('fields.description')} hint={t('wizard.description_hint')}>
                  <textarea
                    rows={4}
                    className="w-full rounded-md border border-stone-300 bg-white px-3 py-2 text-sm dark:border-stone-700 dark:bg-stone-900"
                    value={form.description}
                    onChange={(e) => setForm({ ...form, description: e.target.value })}
                  />
                </Field>
              </>
            )}

            {step === 2 && (
              <div className="space-y-3">
                <p className="text-sm text-stone-500">{t('wizard.references_intro')}</p>
                <Choice
                  checked={references === 'import'}
                  onChange={() => setReferences('import')}
                  title={t('wizard.references_import')}
                  hint={t('wizard.references_import_hint')}
                />
                <Choice
                  checked={references === 'later'}
                  onChange={() => setReferences('later')}
                  title={t('wizard.references_later')}
                  hint={t('wizard.references_later_hint')}
                />
              </div>
            )}

            {step === 3 && (
              <div className="space-y-3">
                <Choice
                  checked={team === 'alone'}
                  onChange={() => setTeam('alone')}
                  title={t('wizard.team_alone')}
                  hint={t('wizard.team_alone_hint')}
                />
                <Choice
                  checked={team === 'invite'}
                  onChange={() => setTeam('invite')}
                  title={t('wizard.team_invite')}
                  hint={t('wizard.team_invite_hint')}
                />
                {team === 'invite' && (
                  <div className="space-y-2 pl-1">
                    {invites.map((inv, i) => (
                      <div key={i} className="grid gap-2 sm:grid-cols-[1fr_11rem]">
                        <Input
                          type="email"
                          aria-label={t('wizard.invite_email')}
                          placeholder={t('wizard.invite_email')}
                          value={inv.email}
                          onChange={(e) => setInvite(i, { email: e.target.value })}
                        />
                        <Select
                          aria-label={t('wizard.invite_role')}
                          value={inv.role}
                          onChange={(e) => setInvite(i, { role: e.target.value as Role })}
                        >
                          {ROLES.map((r) => (
                            <option key={r} value={r}>
                              {t(`role.${r}`)}
                            </option>
                          ))}
                        </Select>
                      </div>
                    ))}
                    {invites.length < MAX_INVITES && (
                      <Button
                        type="button"
                        variant="ghost"
                        onClick={() => setInvites([...invites, { email: '', role: 'reviewer' }])}
                      >
                        + {t('wizard.invite_add')}
                      </Button>
                    )}
                  </div>
                )}
              </div>
            )}

            {step === 4 && (
              <div className="space-y-3">
                <p className="text-sm text-stone-500">{t('wizard.ai_intro')}</p>
                {!aiAvailable && (
                  <p className="rounded-md bg-amber-50 p-3 text-sm text-amber-800 dark:bg-amber-950 dark:text-amber-200">
                    {t('wizard.ai_unavailable')}
                  </p>
                )}
                <Choice
                  checked={ai === 'on' && aiAvailable}
                  disabled={!aiAvailable}
                  onChange={() => setAi('on')}
                  title={t('wizard.ai_on')}
                  hint={t('wizard.ai_on_hint')}
                />
                <Choice
                  checked={ai === 'off' || !aiAvailable}
                  onChange={() => setAi('off')}
                  title={t('wizard.ai_off')}
                  hint={t('wizard.ai_off_hint')}
                />
                <p className="rounded-md bg-stone-100 p-3 text-xs text-stone-600 dark:bg-stone-800 dark:text-stone-300">
                  {t('wizard.ai_where')}
                </p>
              </div>
            )}

            <ErrorText error={error} />
            <div className="flex justify-between gap-2 border-t border-stone-200 pt-4 dark:border-stone-800">
              <Button type="button" variant="ghost" onClick={step === 1 ? onClose : () => setStep((step - 1) as Step)}>
                {step === 1 ? t('projects.cancel') : t('wizard.back')}
              </Button>
              <Button type="submit" disabled={busy || (step === 1 && !form.title.trim())}>
                {step === 4 ? t('wizard.create') : t('wizard.next')}
              </Button>
            </div>
          </form>
        )}

        {step === 'done' && created && (
          <div className="space-y-5 px-6 py-6">
            <p className="text-sm">{t('wizard.done', { title: created.project.title })}</p>
            <p className="text-sm text-stone-500">
              {ai === 'on' && aiAvailable ? t('wizard.done_ai_on') : t('wizard.done_ai_off')}
            </p>
            {created.links.length > 0 && (
              <div className="space-y-2">
                <p className="text-sm font-medium">{t('wizard.invite_links')}</p>
                {created.links.map((l) => (
                  <div key={l.id} className="space-y-1">
                    <p className="text-xs text-stone-500">{l.email}</p>
                    <Input readOnly value={l.invite_url} onFocus={(e) => e.target.select()} />
                  </div>
                ))}
              </div>
            )}
            <div className="flex justify-end border-t border-stone-200 pt-4 dark:border-stone-800">
              <Button onClick={open}>{t('wizard.open')}</Button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
