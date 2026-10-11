import type { Ref } from 'react'
import { useTranslation } from 'react-i18next'
import type { Prisma } from '../api/types'

// Medidas do diagrama (em unidades do SVG)
const W = 780
const BAR = 34
const LEFT_X = BAR + 18
const LEFT_W = 340
const RIGHT_X = LEFT_X + LEFT_W + 50
const RIGHT_W = W - RIGHT_X - 4
const LINE = 18
const PAD = 12
const ARROW_GAP = 36

const cut = (s: string, n = 44) => (s.length > n ? `${s.slice(0, n - 1)}…` : s)

interface Box {
  lines: string[]
  bold?: number
}

function boxHeight(b: Box | null) {
  return b ? b.lines.length * LINE + PAD * 2 : 0
}

function TextBox({ x, y, w, h, box }: { x: number; y: number; w: number; h: number; box: Box }) {
  return (
    <g>
      <rect x={x} y={y} width={w} height={h} fill="#fff" stroke="#44403c" strokeWidth={1.2} />
      {box.lines.map((l, i) => (
        <text
          key={i}
          x={x + PAD}
          y={y + (h - box.lines.length * LINE) / 2 + LINE * i + 13}
          fontSize={13}
          fontWeight={i < (box.bold ?? 1) ? 600 : 400}
          fill="#1c1917"
        >
          {l}
        </text>
      ))}
    </g>
  )
}

export function PrismaDiagram({ data, ref }: { data: Prisma; ref?: Ref<SVGSVGElement> }) {
  const { t, i18n } = useTranslation()
  const n = (v: number) => `(n = ${v.toLocaleString(i18n.language)})`
  const id = data.identification
  const el = data.eligibility

  const rows: { left: Box; right: Box | null }[] = [
    {
      left: {
        lines: [
          t('prisma.identified'),
          `${t('prisma.databases')} ${n(id.total)}`,
          ...id.by_source.map((s) => `  ${cut(s.source, 30)} ${n(s.records)}`),
        ],
      },
      right: {
        lines: [t('prisma.removed_before'), `${t('prisma.duplicates')} ${n(id.duplicates_removed)}`],
      },
    },
    {
      left: { lines: [`${t('prisma.screened')} ${n(data.screening.screened)}`] },
      right: { lines: [`${t('prisma.excluded')} ${n(data.screening.excluded)}`] },
    },
    {
      left: { lines: [`${t('prisma.sought')} ${n(data.retrieval.sought)}`] },
      right: { lines: [`${t('prisma.not_retrieved')} ${n(data.retrieval.not_retrieved)}`] },
    },
    {
      left: { lines: [`${t('prisma.assessed')} ${n(el.assessed)}`] },
      right: {
        lines: [
          `${t('prisma.reports_excluded')} ${n(el.excluded)}`,
          ...el.reasons.map((r) => `  ${cut(r.reason ?? t('prisma.no_reason'), 26)} ${n(r.count)}`),
        ],
      },
    },
    { left: { lines: [`${t('prisma.included')} ${n(data.included)}`] }, right: null },
  ]

  // Posição vertical de cada linha do diagrama
  let y = 4
  const laid = rows.map((r) => {
    // A última linha fica alta o bastante para caber o rótulo vertical da fase
    const h = Math.max(boxHeight(r.left), boxHeight(r.right), r.right ? 0 : 84)
    const out = { ...r, y, h }
    y += h + ARROW_GAP
    return out
  })
  const height = y - ARROW_GAP + 4
  const pending = data.screening.pending + el.pending

  const bars = [
    { label: t('prisma.phase_identification'), from: 0, to: 0 },
    { label: t('prisma.phase_screening'), from: 1, to: 3 },
    { label: t('prisma.phase_included'), from: 4, to: 4 },
  ]

  return (
    <svg
      ref={ref}
      xmlns="http://www.w3.org/2000/svg"
      viewBox={`0 0 ${W} ${height + (pending ? 30 : 0)}`}
      width="100%"
      fontFamily="Inter, Arial, sans-serif"
      role="img"
      aria-label={t('prisma.title')}
    >
      <rect width="100%" height="100%" fill="#fff" />
      <defs>
        <marker id="prisma-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
          <path d="M0,0 L10,5 L0,10 z" fill="#44403c" />
        </marker>
      </defs>
      {bars.map((b) => {
        const top = laid[b.from].y
        const bottom = laid[b.to].y + laid[b.to].h
        const cy = (top + bottom) / 2
        return (
          <g key={b.label}>
            <rect x={0} y={top} width={BAR} height={bottom - top} rx={4} fill="#d6e9e2" />
            <text
              x={BAR / 2}
              y={cy}
              fontSize={13}
              fontWeight={600}
              fill="#1f4f43"
              textAnchor="middle"
              dominantBaseline="central"
              transform={`rotate(-90 ${BAR / 2} ${cy})`}
            >
              {b.label}
            </text>
          </g>
        )
      })}
      {laid.map((r, i) => (
        <g key={i}>
          <TextBox x={LEFT_X} y={r.y} w={LEFT_W} h={r.h} box={r.left} />
          {r.right && (
            <>
              <TextBox x={RIGHT_X} y={r.y} w={RIGHT_W} h={r.h} box={r.right} />
              <line
                x1={LEFT_X + LEFT_W}
                y1={r.y + r.h / 2}
                x2={RIGHT_X}
                y2={r.y + r.h / 2}
                stroke="#44403c"
                strokeWidth={1.2}
                markerEnd="url(#prisma-arrow)"
              />
            </>
          )}
          {i < laid.length - 1 && (
            <line
              x1={LEFT_X + LEFT_W / 2}
              y1={r.y + r.h}
              x2={LEFT_X + LEFT_W / 2}
              y2={laid[i + 1].y}
              stroke="#44403c"
              strokeWidth={1.2}
              markerEnd="url(#prisma-arrow)"
            />
          )}
        </g>
      ))}
      {pending > 0 && (
        <text x={LEFT_X} y={height + 18} fontSize={12} fill="#b45309">
          {t('prisma.pending_note', { count: pending })}
        </text>
      )}
    </svg>
  )
}
