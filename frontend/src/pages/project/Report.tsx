import { useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { exportUrl, usePrisma } from '../../api/reports'
import { Button, Card, Field, Select } from '../../components/ui'
import { PrismaDiagram } from '../../components/PrismaDiagram'
import { savePng, saveSvg } from '../../lib/download'
import { useProjectContext } from './context'
import { ChecklistSection } from './ChecklistSection'
import { ReportDocument } from './ReportDocument'

const STATES = ['all', 'included', 'excluded', 'conflict', 'pending'] as const

export default function Report() {
  const { t } = useTranslation()
  const { project } = useProjectContext()
  const { data } = usePrisma(project.id)
  const svgRef = useRef<SVGSVGElement>(null)
  const [phase, setPhase] = useState('title_abstract')
  const [state, setState] = useState<(typeof STATES)[number]>('included')


  return (
    <div className="space-y-6">
      <Card className="space-y-4 p-4">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="mr-auto font-semibold">{t('prisma.title')}</h2>
          <Button variant="ghost" onClick={() => saveSvg(svgRef.current, 'prisma-2020')} disabled={!data}>
            {t('prisma.download_svg')}
          </Button>
          <Button variant="ghost" onClick={() => void savePng(svgRef.current, 'prisma-2020')} disabled={!data}>
            {t('prisma.download_png')}
          </Button>
        </div>
        <p className="text-sm text-stone-500">{t('prisma.hint')}</p>
        <div className="overflow-x-auto rounded-md border border-stone-200 dark:border-stone-800">
          <div className="min-w-[640px]">{data && <PrismaDiagram ref={svgRef} data={data} />}</div>
        </div>
      </Card>

      <ReportDocument />

      <Card className="space-y-4 p-4">
        <h2 className="font-semibold">{t('export.title')}</h2>
        <p className="text-sm text-stone-500">{t('export.hint')}</p>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label={t('export.phase')}>
            <Select value={phase} onChange={(e) => setPhase(e.target.value)}>
              <option value="title_abstract">{t('screening.phase_title_abstract')}</option>
              <option value="full_text">{t('screening.phase_full_text')}</option>
            </Select>
          </Field>
          <Field label={t('export.state')}>
            <Select value={state} onChange={(e) => setState(e.target.value as (typeof STATES)[number])}>
              {STATES.map((s) => (
                <option key={s} value={s}>
                  {s === 'all' ? t('screening.all_records') : t(`state.${s}`)}
                </option>
              ))}
            </Select>
          </Field>
        </div>
        <div className="flex flex-wrap gap-2">
          <a
            href={exportUrl(project.id, 'ris', phase, state)}
            className="rounded-md bg-brand-600 px-3 py-2 text-sm font-medium text-white hover:bg-brand-700"
          >
            {t('export.ris')}
          </a>
          <a
            href={exportUrl(project.id, 'csv', phase, state)}
            className="rounded-md px-3 py-2 text-sm font-medium text-stone-700 hover:bg-stone-200 dark:text-stone-300 dark:hover:bg-stone-800"
          >
            {t('export.csv')}
          </a>
        </div>
      </Card>
      <ChecklistSection />
    </div>
  )
}
