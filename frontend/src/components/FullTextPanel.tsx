import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { fileUrl, useFileActions, useRecordFiles } from '../api/files'
import { PdfViewer, type PdfFocus, type PdfSelection } from './PdfViewer'
import { Button, Card, ErrorText } from './ui'

export function FullTextPanel({
  pid,
  rid,
  include,
  exclude,
  canUpload,
  focus,
  onClearFocus,
  onSelect,
}: {
  pid: string
  rid: string
  include: string[]
  exclude: string[]
  canUpload: boolean
  /** Página e trecho a destacar, num arquivo específico */
  focus?: (PdfFocus & { fileId: string | null }) | null
  onClearFocus?: () => void
  /** Texto selecionado no PDF aberto */
  onSelect?: (sel: PdfSelection & { fileId: string }) => void
}) {
  const { t } = useTranslation()
  const files = useRecordFiles(pid, rid)
  const { upload, remove, makeMain } = useFileActions(pid)
  const [chosen, setChosen] = useState<string | null>(null)
  const list = files.data ?? []
  const current =
    list.find((f) => f.id === (focus?.fileId ?? chosen)) ?? list.find((f) => f.is_main) ?? list[0]

  const uploader = canUpload && (
    <label className="inline-flex cursor-pointer items-center gap-2 text-sm text-brand-600 dark:text-brand-300 hover:underline">
      <input
        type="file"
        accept="application/pdf,.pdf"
        className="sr-only"
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file) upload.mutate({ rid, file })
          e.target.value = ''
        }}
      />
      {list.length ? t('pdf.add_another') : t('pdf.upload')}
    </label>
  )

  if (files.isLoading) return null
  if (!current)
    return (
      <Card className="space-y-2 text-center">
        <p className="text-stone-500">{t('pdf.none')}</p>
        {uploader}
        {upload.isPending && <p className="text-sm text-stone-500">{t('pdf.uploading')}</p>}
        <ErrorText error={upload.error} />
      </Card>
    )

  return (
    <Card className="min-w-0 overflow-hidden p-0!">
      <div className="flex flex-wrap items-center gap-3 border-b border-stone-200 px-3 py-2 text-sm dark:border-stone-800">
        {list.length > 1 ? (
          <select
            aria-label={t('pdf.file')}
            className="rounded border border-stone-300 bg-transparent px-2 py-1 dark:border-stone-700"
            value={current.id}
            onChange={(e) => {
              setChosen(e.target.value)
              onClearFocus?.()
            }}
          >
            {list.map((f) => (
              <option key={f.id} value={f.id}>
                {f.filename}
                {f.is_main ? ` (${t('pdf.main')})` : ''}
              </option>
            ))}
          </select>
        ) : (
          <span className="truncate font-medium">{current.filename}</span>
        )}
        {!current.has_text && <span className="text-amber-700 dark:text-amber-300">{t('pdf.no_text')}</span>}
        {current.source === 'open_access' && <span className="text-stone-500">{t('pdf.open_access')}</span>}
        <span className="ml-auto flex items-center gap-3">
          {uploader}
          {canUpload && !current.is_main && (
            <Button variant="ghost" onClick={() => makeMain.mutate(current.id)}>
              {t('pdf.make_main')}
            </Button>
          )}
          {canUpload && (
            <Button
              variant="danger"
              onClick={() => window.confirm(t('pdf.delete_confirm')) && remove.mutate(current.id)}
            >
              {t('pdf.delete')}
            </Button>
          )}
        </span>
      </div>
      <ErrorText error={upload.error ?? remove.error ?? makeMain.error} />
      <div className="h-[80vh]">
        <PdfViewer
          key={current.id}
          url={fileUrl(pid, current.id)}
          include={include}
          exclude={exclude}
          focus={focus && (!focus.fileId || focus.fileId === current.id) ? focus : null}
          onSelect={onSelect && ((sel) => onSelect({ ...sel, fileId: current.id }))}
        />
      </div>
    </Card>
  )
}
