import { useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { exportUrl, usePrisma } from '../../api/reports'
import { Button, Card, Field, Select } from '../../components/ui'
import { PrismaDiagram } from '../../components/PrismaDiagram'
import { useProjectContext } from './context'

const STATES = ['all', 'included', 'excluded', 'conflict', 'pending'] as const

function download(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  URL.revokeObjectURL(url)
}

function svgText(svg: SVGSVGElement) {
  return '<?xml version="1.0" encoding="UTF-8"?>\n' + new XMLSerializer().serializeToString(svg)
}

async function svgToPng(svg: SVGSVGElement): Promise<Blob | null> {
  const box = svg.viewBox.baseVal
  const scale = 2
  const img = new Image()
  img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svgText(svg))
  await img.decode()
  const canvas = document.createElement('canvas')
  canvas.width = box.width * scale
  canvas.height = box.height * scale
  const ctx = canvas.getContext('2d')
  if (!ctx) return null
  ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
  return new Promise((resolve) => canvas.toBlob(resolve, 'image/png'))
}

export default function Report() {
  const { t } = useTranslation()
  const { project } = useProjectContext()
  const { data } = usePrisma(project.id)
  const svgRef = useRef<SVGSVGElement>(null)
  const [phase, setPhase] = useState('title_abstract')
  const [state, setState] = useState<(typeof STATES)[number]>('included')

  const saveSvg = () => {
    if (svgRef.current)
      download(new Blob([svgText(svgRef.current)], { type: 'image/svg+xml' }), 'prisma-2020.svg')
  }
  const savePng = async () => {
    if (!svgRef.current) return
    const blob = await svgToPng(svgRef.current)
    if (blob) download(blob, 'prisma-2020.png')
  }

  return (
    <div className="space-y-6">
      <Card className="space-y-4 p-4">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="mr-auto font-semibold">{t('prisma.title')}</h2>
          <Button variant="ghost" onClick={saveSvg} disabled={!data}>
            {t('prisma.download_svg')}
          </Button>
          <Button variant="ghost" onClick={() => void savePng()} disabled={!data}>
            {t('prisma.download_png')}
          </Button>
        </div>
        <p className="text-sm text-stone-500">{t('prisma.hint')}</p>
        <div className="overflow-x-auto rounded-md border border-stone-200 dark:border-stone-800">
          <div className="min-w-[640px]">{data && <PrismaDiagram ref={svgRef} data={data} />}</div>
        </div>
      </Card>

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
    </div>
  )
}
