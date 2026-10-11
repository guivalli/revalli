import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { useInstanceAI, useProviderActions, useProviders, type ProviderPayload } from '../api/ai'
import { useMe } from '../api/hooks'
import type { InstanceAISettings, Provider, ProviderKind, TaskModel } from '../api/types'
import { Button, Card, ErrorText, Field, Input, Select } from '../components/ui'

const PRESETS: Record<ProviderKind, { url: string; local: boolean; key: boolean }> = {
  ollama: { url: 'http://ollama:11434/v1', local: true, key: false },
  openai: { url: 'https://api.openai.com/v1', local: false, key: true },
  anthropic: { url: 'https://api.anthropic.com/v1', local: false, key: true },
  google: { url: 'https://generativelanguage.googleapis.com/v1beta/openai', local: false, key: true },
  openrouter: { url: 'https://openrouter.ai/api/v1', local: false, key: true },
  custom: { url: '', local: false, key: true },
}

const empty: ProviderPayload = { name: '', kind: 'ollama', base_url: PRESETS.ollama.url, is_local: true }

function ProviderForm({ initial, onDone }: { initial?: Provider; onDone: () => void }) {
  const { t } = useTranslation()
  const { create, update } = useProviderActions()
  const [p, setP] = useState<ProviderPayload>(
    initial
      ? { name: initial.name, kind: initial.kind, base_url: initial.base_url, is_local: initial.is_local }
      : empty,
  )
  const [key, setKey] = useState('')
  const mut = initial ? update : create
  const submit = (e: FormEvent) => {
    e.preventDefault()
    const body = { ...p, api_key: key }
    const opts = { onSuccess: onDone }
    if (initial) update.mutate({ id: initial.id, body }, opts)
    else create.mutate(body, opts)
  }
  return (
    <form onSubmit={submit} className="space-y-4 rounded-md border border-stone-200 p-4 dark:border-stone-800">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t('ai.kind')}>
          <Select
            value={p.kind}
            onChange={(e) => {
              const kind = e.target.value as ProviderKind
              setP({ ...p, kind, base_url: PRESETS[kind].url, is_local: PRESETS[kind].local })
            }}
          >
            {(Object.keys(PRESETS) as ProviderKind[]).map((k) => (
              <option key={k} value={k}>
                {t(`ai.kinds.${k}`)}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={t('ai.name')}>
          <Input required value={p.name} onChange={(e) => setP({ ...p, name: e.target.value })} />
        </Field>
        <Field label={t('ai.base_url')} hint={t('ai.base_url_hint')}>
          <Input
            required
            type="url"
            value={p.base_url}
            onChange={(e) => setP({ ...p, base_url: e.target.value })}
          />
        </Field>
        <Field
          label={t('ai.api_key')}
          hint={initial?.api_key_hint ? t('ai.api_key_keep', { hint: initial.api_key_hint }) : t('ai.api_key_hint')}
        >
          <Input type="password" autoComplete="off" value={key} onChange={(e) => setKey(e.target.value)} />
        </Field>
      </div>
      <label className="flex items-start gap-3">
        <input
          type="checkbox"
          className="mt-1 size-4 accent-brand-600"
          checked={p.is_local}
          onChange={(e) => setP({ ...p, is_local: e.target.checked })}
        />
        <span>
          <span className="block text-sm font-medium">{t('ai.is_local')}</span>
          <span className="block text-xs text-stone-500">{t('ai.is_local_hint')}</span>
        </span>
      </label>
      <ErrorText error={mut.error} />
      <div className="flex gap-2">
        <Button type="submit" disabled={mut.isPending}>
          {t('ai.save_provider')}
        </Button>
        <Button type="button" variant="ghost" onClick={onDone}>
          {t('ai.cancel')}
        </Button>
      </div>
    </form>
  )
}

function ProviderRow({ p, onEdit }: { p: Provider; onEdit: () => void }) {
  const { t } = useTranslation()
  const { test, remove } = useProviderActions()
  return (
    <li className="space-y-1 border-t border-stone-100 py-3 first:border-0 dark:border-stone-800">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium">{p.name}</span>
        <span className="rounded-full bg-stone-100 px-2 text-xs dark:bg-stone-800">
          {p.is_local ? t('ai.local') : t('ai.remote')}
        </span>
        <span className="text-xs text-stone-500">{p.base_url}</span>
        {p.api_key_hint && <span className="text-xs text-stone-500">🔑 {p.api_key_hint}</span>}
        <span className="ml-auto flex gap-1">
          <Button variant="ghost" onClick={() => test.mutate(p.id)} disabled={test.isPending}>
            {t('ai.test')}
          </Button>
          <Button variant="ghost" onClick={onEdit}>
            {t('ai.edit')}
          </Button>
          <Button
            variant="danger"
            onClick={() => window.confirm(t('ai.delete_confirm', { name: p.name })) && remove.mutate(p.id)}
          >
            {t('ai.delete')}
          </Button>
        </span>
      </div>
      {test.isSuccess && (
        <p role="status" className="text-xs text-brand-700 dark:text-brand-100">
          {t('ai.test_ok', { count: test.data.length })} {test.data.slice(0, 12).join(', ')}
        </p>
      )}
      <ErrorText error={test.error} />
    </li>
  )
}

function TaskForm({
  label,
  hint,
  value,
  providers,
  onChange,
}: {
  label: string
  hint: string
  value: TaskModel
  providers: Provider[]
  onChange: (v: TaskModel) => void
}) {
  const { t } = useTranslation()
  const local = providers.find((p) => p.id === value.provider_id)?.is_local
  return (
    <fieldset className="space-y-3">
      <legend className="font-medium">{label}</legend>
      <p className="text-xs text-stone-500">{hint}</p>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t('ai.provider')}>
          <Select
            value={value.provider_id ?? ''}
            onChange={(e) => onChange({ ...value, provider_id: e.target.value || null })}
          >
            <option value="">{t('ai.none')}</option>
            {providers.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={t('ai.model')} hint={t('ai.model_hint')}>
          <Input value={value.model} onChange={(e) => onChange({ ...value, model: e.target.value })} />
        </Field>
        {value.provider_id && !local && (
          <>
            <Field label={t('ai.price_input')}>
              <Input
                type="number"
                min={0}
                step="0.01"
                value={value.price_input}
                onChange={(e) => onChange({ ...value, price_input: Number(e.target.value) })}
              />
            </Field>
            <Field label={t('ai.price_output')}>
              <Input
                type="number"
                min={0}
                step="0.01"
                value={value.price_output}
                onChange={(e) => onChange({ ...value, price_output: Number(e.target.value) })}
              />
            </Field>
          </>
        )}
      </div>
    </fieldset>
  )
}

function ModelsForm({ initial, providers }: { initial: InstanceAISettings; providers: Provider[] }) {
  const { t } = useTranslation()
  const { saveSettings } = useProviderActions()
  const [s, setS] = useState(initial)
  return (
    <Card className="space-y-5">
      <h2 className="font-semibold">{t('ai.models_title')}</h2>
      <TaskForm
        label={t('ai.task_screening')}
        hint={t('ai.task_screening_hint')}
        value={s.screening}
        providers={providers}
        onChange={(v) => setS({ ...s, screening: v })}
      />
      <TaskForm
        label={t('ai.task_embeddings')}
        hint={t('ai.task_embeddings_hint')}
        value={s.embeddings}
        providers={providers}
        onChange={(v) => setS({ ...s, embeddings: v })}
      />
      <TaskForm
        label={t('ai.task_extraction')}
        hint={t('ai.task_extraction_hint')}
        value={s.extraction}
        providers={providers}
        onChange={(v) => setS({ ...s, extraction: v })}
      />
      <ErrorText error={saveSettings.error} />
      {saveSettings.isSuccess && (
        <p role="status" className="text-sm text-brand-700 dark:text-brand-100">
          {t('ai.saved')}
        </p>
      )}
      <Button onClick={() => saveSettings.mutate(s)} disabled={saveSettings.isPending}>
        {t('ai.save_models')}
      </Button>
    </Card>
  )
}

export default function AISettings() {
  const { t } = useTranslation()
  const { data: me } = useMe()
  const providers = useProviders(!!me?.is_admin)
  const settings = useInstanceAI()
  const [editing, setEditing] = useState<string | 'new' | null>(null)

  if (!me?.is_admin) return <p>{t('errors.admin_only')}</p>
  const list = providers.data ?? []
  return (
    <div className="space-y-6">
      <div>
        <Link to="/" className="text-sm text-brand-600 hover:underline">
          ← {t('projects.back')}
        </Link>
        <h1 className="mt-2 text-2xl font-semibold">{t('ai.title')}</h1>
        <p className="text-sm text-stone-500">{t('ai.intro')}</p>
      </div>
      <Card className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold">{t('ai.providers')}</h2>
          {editing === null && <Button onClick={() => setEditing('new')}>{t('ai.add_provider')}</Button>}
        </div>
        {editing === 'new' && <ProviderForm onDone={() => setEditing(null)} />}
        {list.length === 0 && editing !== 'new' && <p className="text-sm text-stone-500">{t('ai.no_providers')}</p>}
        <ul>
          {list.map((p) =>
            editing === p.id ? (
              <li key={p.id} className="py-3">
                <ProviderForm initial={p} onDone={() => setEditing(null)} />
              </li>
            ) : (
              <ProviderRow key={p.id} p={p} onEdit={() => setEditing(p.id)} />
            ),
          )}
        </ul>
      </Card>
      {settings.data && providers.data && (
        <ModelsForm key={JSON.stringify(providers.data.map((p) => p.id))} initial={settings.data} providers={list} />
      )}
    </div>
  )
}
