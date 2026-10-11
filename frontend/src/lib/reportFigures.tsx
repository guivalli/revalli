import type { i18n as I18n } from 'i18next'
import type { ReactNode } from 'react'
import { flushSync } from 'react-dom'
import { createRoot } from 'react-dom/client'
import { I18nextProvider } from 'react-i18next'
import { api } from '../api/client'
import type { MetaAnalysisT, MetaResult, Prisma } from '../api/types'
import { ForestPlot } from '../components/MetaPlots'
import { PrismaDiagram } from '../components/PrismaDiagram'
import { svgToPng } from './download'

/** Desenha um gráfico fora da tela, no idioma pedido, e devolve o PNG em base64. */
async function snapshot(i18n: I18n, width: number, node: ReactNode): Promise<string | null> {
  const host = document.createElement('div')
  host.style.cssText = `position:fixed;left:-20000px;top:0;width:${width}px;background:#fff;color:#1c1917`
  document.body.appendChild(host)
  const root = createRoot(host)
  try {
    flushSync(() => root.render(<I18nextProvider i18n={i18n}>{node}</I18nextProvider>))
    const svg = host.querySelector('svg')
    const blob = svg ? await svgToPng(svg) : null
    return blob ? await toBase64(blob) : null
  } finally {
    root.unmount()
    host.remove()
  }
}

function toBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result))
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(blob)
  })
}

/** Fluxograma PRISMA e forest plot de cada meta-análise, para o relatório em DOCX/PDF. */
export async function reportFigures(pid: string, i18n: I18n): Promise<Record<string, string>> {
  const out: Record<string, string> = {}
  const prisma = await api.get<Prisma>(`/projects/${pid}/report/prisma`)
  const png = await snapshot(i18n, 760, <PrismaDiagram data={prisma} />)
  if (png) out.prisma = png
  const analyses = await api.get<MetaAnalysisT[]>(`/projects/${pid}/meta`)
  for (const a of analyses) {
    const result = await api.get<MetaResult>(`/projects/${pid}/meta/${a.id}/result`)
    if (!result.pooled) continue
    const forest = await snapshot(i18n, 900, <ForestPlot analysis={a} result={result} />)
    if (forest) out[`meta:${a.id}`] = forest
  }
  return out
}
