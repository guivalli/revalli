import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../../api/client'
import { Button, Card, ErrorText, Field, Select } from '../../components/ui'
import { LANGUAGES } from '../../i18n'
import { CHECKLIST_SECTIONS } from '../../lib/checklists'
import { download } from '../../lib/download'
import { reportFigures } from '../../lib/reportFigures'
import { useProjectContext } from './context'

const SECTIONS = ['methods', 'results', 'appendix_search', 'appendix_ai', 'appendix_checklist'] as const
type Lang = keyof typeof LANGUAGES

export function ReportDocument() {
  const { t, i18n } = useTranslation()
  const { project } = useProjectContext()
  const [format, setFormat] = useState<'docx' | 'pdf'>('docx')
  const [lang, setLang] = useState<Lang>(i18n.language === 'en' ? 'en' : 'pt-BR')
  const [sections, setSections] = useState<Set<string>>(new Set(SECTIONS))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)

  const generate = async () => {
    setBusy(true)
    setError(null)
    try {
      const fixed = i18n.cloneInstance({ lng: lang })
      const figures = sections.has('results') ? await reportFigures(project.id, fixed) : {}
      const kind = project.review_type === 'scoping' ? 'prisma_scr' : 'prisma2020'
      const items = Object.values(CHECKLIST_SECTIONS[kind]).flat() as string[]
      const checklist_items = Object.fromEntries(items.map((i) => [i, fixed.t(`checklist_items.${kind}.${i}`)]))
      const file = await api.download(`/projects/${project.id}/report/document`, {
        format,
        lang,
        sections: SECTIONS.filter((s) => sections.has(s)),
        figures,
        checklist_items,
      })
      download(file.blob, file.name)
    } catch (e) {
      setError(e)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card className="space-y-4 p-4">
      <div>
        <h2 className="font-semibold">{t('report_doc.title')}</h2>
        <p className="text-sm text-stone-500">{t('report_doc.hint')}</p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t('report_doc.format')}>
          <Select value={format} onChange={(e) => setFormat(e.target.value as 'docx' | 'pdf')}>
            <option value="docx">{t('report_doc.docx')}</option>
            <option value="pdf">PDF</option>
          </Select>
        </Field>
        <Field label={t('report_doc.language')}>
          <Select value={lang} onChange={(e) => setLang(e.target.value as Lang)}>
            {Object.entries(LANGUAGES).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </Select>
        </Field>
      </div>
      <fieldset className="flex flex-wrap gap-x-5 gap-y-2 text-sm">
        <legend className="mb-1 text-sm font-medium">{t('report_doc.sections')}</legend>
        {SECTIONS.map((s) => (
          <label key={s} className="flex items-center gap-2">
            <input
              type="checkbox"
              className="accent-brand-600"
              checked={sections.has(s)}
              onChange={() => {
                const next = new Set(sections)
                if (next.has(s)) next.delete(s)
                else next.add(s)
                setSections(next)
              }}
            />
            {t(`report_doc.section_${s}`)}
          </label>
        ))}
      </fieldset>
      <ErrorText error={error} />
      <Button disabled={busy || sections.size === 0} onClick={() => void generate()}>
        {busy ? t('report_doc.generating') : t('report_doc.generate')}
      </Button>
    </Card>
  )
}
