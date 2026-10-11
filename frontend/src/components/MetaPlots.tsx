import type { Ref } from 'react'
import { useTranslation } from 'react-i18next'
import type { MetaAnalysisT, MetaResult, MetaRow, PooledT } from '../api/types'
import { useFmt, useFmtP } from '../lib/format'

const FONT = 'Inter, Helvetica, Arial, sans-serif'
const INK = '#1c1917'
const MUTED = '#57534e'
const ROW = 20

/** Marcas "redondas" para um eixo linear. */
function linearTicks(lo: number, hi: number, count = 5): number[] {
  const span = hi - lo || 1
  const raw = span / count
  const mag = 10 ** Math.floor(Math.log10(raw))
  const step = [1, 2, 5, 10].map((m) => m * mag).find((s) => span / s <= count) ?? 10 * mag
  const out = []
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(10))
  return out
}

const LOG_TICKS = [0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100]

function makeScale(values: number[], log: boolean, x0: number, width: number) {
  const nullValue = log ? 1 : 0
  const finite = values.filter((v) => Number.isFinite(v) && (!log || v > 0))
  let lo = Math.min(nullValue, ...finite)
  let hi = Math.max(nullValue, ...finite)
  if (log) {
    lo = Math.max(lo, 0.01)
    hi = Math.min(hi, 100)
    const t = (v: number) => Math.log(Math.min(Math.max(v, lo), hi))
    const a = t(lo) - 0.05 * (t(hi) - t(lo) || 1)
    const b = t(hi) + 0.05 * (t(hi) - t(lo) || 1)
    let ticks = LOG_TICKS.filter((v) => v >= Math.exp(a) && v <= Math.exp(b))
    if (ticks.length > 7) ticks = ticks.filter((v) => [0.01, 0.1, 0.5, 1, 2, 10, 100].includes(v))
    return {
      x: (v: number) => x0 + ((Math.log(Math.min(Math.max(v, 1e-9), 1e9)) - a) / (b - a)) * width,
      ticks,
      nullValue,
      clamp: (v: number) => Math.min(Math.max(v, Math.exp(a)), Math.exp(b)),
    }
  }
  const pad = 0.05 * (hi - lo || 1)
  lo -= pad
  hi += pad
  return {
    x: (v: number) => x0 + ((v - lo) / (hi - lo)) * width,
    ticks: linearTicks(lo, hi),
    nullValue,
    clamp: (v: number) => Math.min(Math.max(v, lo), hi),
  }
}

function dataCells(measure: string, row: MetaRow | undefined, fmt: (v: number | null | undefined, d?: number) => string) {
  if (!row) return ['', '']
  if (['RR', 'OR', 'RD'].includes(measure))
    return [`${row.e1 ?? '–'}/${row.n1 ?? '–'}`, `${row.e2 ?? '–'}/${row.n2 ?? '–'}`]
  if (['MD', 'SMD'].includes(measure))
    return [`${fmt(row.mean1, 1)} (${fmt(row.sd1, 1)}) ${row.n1 ?? ''}`, `${fmt(row.mean2, 1)} (${fmt(row.sd2, 1)}) ${row.n2 ?? ''}`]
  return null
}

function Diamond({ p, y, scale }: { p: PooledT; y: number; scale: ReturnType<typeof makeScale> }) {
  const l = scale.x(scale.clamp(p.lower))
  const c = scale.x(scale.clamp(p.estimate))
  const r = scale.x(scale.clamp(p.upper))
  return <polygon points={`${l},${y} ${c},${y - 6} ${r},${y} ${c},${y + 6}`} fill={INK} />
}

export function ForestPlot({
  analysis,
  result,
  ref,
}: {
  analysis: MetaAnalysisT
  result: MetaResult
  ref?: Ref<SVGSVGElement>
}) {
  const { t } = useTranslation()
  const fmt = useFmt()
  const fmtP = useFmtP()
  const rowsById = new Map(analysis.rows.map((r) => [r.id, r]))
  const hasData = dataCells(analysis.measure, undefined, fmt) !== null
  const W = 960
  const PLOT_X = hasData ? 440 : 260
  const PLOT_W = 280
  const EST_X = PLOT_X + PLOT_W + 16
  const WEIGHT_X = W - 10
  const studies = result.studies.filter((s) => s.estimate != null)
  const values = studies.flatMap((s) => [s.lower!, s.upper!])
  if (result.pooled) values.push(result.pooled.lower, result.pooled.upper)
  const scale = makeScale(values, result.log_scale, PLOT_X, PLOT_W)
  const maxW = Math.max(...studies.map((s) => s.weight ?? 0), 1)
  const grouped = result.subgroups.length > 0

  type Line =
    | { kind: 'study'; s: MetaResult['studies'][number] }
    | { kind: 'header'; text: string }
    | { kind: 'pooled'; text: string; p: PooledT; het?: string }
  const lines: Line[] = []
  const het = (p: PooledT) =>
    t('meta.heterogeneity', {
      tau2: fmt(p.tau2, 2),
      i2: fmt(p.i2, 0),
      q: fmt(p.q, 2),
      df: p.df,
      p: fmtP(p.p_q),
    })
  if (grouped) {
    for (const g of result.subgroups) {
      lines.push({ kind: 'header', text: g.name })
      for (const s of result.studies.filter((x) => x.subgroup === g.name)) lines.push({ kind: 'study', s })
      if (g.pooled) lines.push({ kind: 'pooled', text: t('meta.subtotal'), p: g.pooled, het: g.pooled.k > 1 ? het(g.pooled) : undefined })
    }
    const rest = result.studies.filter((x) => !result.subgroups.some((g) => g.name === x.subgroup))
    for (const s of rest) lines.push({ kind: 'study', s })
  } else {
    for (const s of result.studies) lines.push({ kind: 'study', s })
  }
  if (result.pooled) lines.push({ kind: 'pooled', text: t(`meta.model_${result.model}`), p: result.pooled })

  const top = 44
  let y = top
  const laid = lines.map((l) => {
    const h = l.kind === 'pooled' && l.het ? ROW * 2 : l.kind === 'header' ? ROW + 4 : ROW
    const out = { l, y: y + ROW / 2 }
    y += h
    return out
  })
  const axisY = y + 8
  const p = result.pooled
  const footer = [
    p && p.k > 1 ? het(p) : null,
    p ? t('meta.overall_test', { z: fmt(p.z, 2), p: fmtP(p.p) }) : null,
    p?.prediction ? t('meta.prediction', { lower: fmt(p.prediction[0]), upper: fmt(p.prediction[1]) }) : null,
    result.subgroup_test
      ? t('meta.subgroup_test', { q: fmt(result.subgroup_test.q, 2), df: result.subgroup_test.df, p: fmtP(result.subgroup_test.p) })
      : null,
  ].filter(Boolean) as string[]
  const H = axisY + 48 + footer.length * 16 + 8
  const leftLabel = analysis.lower_favours_1 ? analysis.label1 : analysis.label2
  const rightLabel = analysis.lower_favours_1 ? analysis.label2 : analysis.label1
  const measureLabel = t(`meta.measure_short_${analysis.measure}`)

  return (
    <svg ref={ref} xmlns="http://www.w3.org/2000/svg" viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label={t('meta.forest')}>
      <rect width={W} height={H} fill="#fff" />
      <g fontFamily={FONT} fontSize={12} fill={INK}>
        <text x={8} y={20} fontWeight={600}>
          {t('meta.study')}
        </text>
        {hasData && (
          <>
            <text x={220} y={20} fontWeight={600}>
              {analysis.label1 || t('meta.group1')}
            </text>
            <text x={330} y={20} fontWeight={600}>
              {analysis.label2 || t('meta.group2')}
            </text>
          </>
        )}
        <text x={PLOT_X + PLOT_W / 2} y={20} fontWeight={600} textAnchor="middle">
          {measureLabel} ({t('meta.ci95')})
        </text>
        <text x={WEIGHT_X} y={20} fontWeight={600} textAnchor="end">
          {t('meta.weight')}
        </text>
        <line x1={0} x2={W} y1={30} y2={30} stroke="#d6d3d1" />
        <line
          x1={scale.x(scale.nullValue)}
          x2={scale.x(scale.nullValue)}
          y1={top - 6}
          y2={axisY}
          stroke={MUTED}
          strokeWidth={0.8}
        />
        {result.pooled && (
          <line
            x1={scale.x(scale.clamp(result.pooled.estimate))}
            x2={scale.x(scale.clamp(result.pooled.estimate))}
            y1={top - 6}
            y2={axisY}
            stroke="#a8a29e"
            strokeDasharray="3 3"
          />
        )}
        {laid.map(({ l, y }, i) => {
          if (l.kind === 'header')
            return (
              <text key={i} x={8} y={y + 6} fontWeight={600}>
                {l.text}
              </text>
            )
          if (l.kind === 'pooled')
            return (
              <g key={i}>
                <text x={8} y={y + 4} fontWeight={600}>
                  {l.text}
                </text>
                {l.p.participants != null && hasData && (
                  <text x={220} y={y + 4} fill={MUTED}>
                    {t('meta.participants_short', { n: l.p.participants })}
                  </text>
                )}
                <Diamond p={l.p} y={y} scale={scale} />
                <text x={EST_X} y={y + 4} fontWeight={600}>
                  {fmt(l.p.estimate)} [{fmt(l.p.lower)}; {fmt(l.p.upper)}]
                </text>
                <text x={WEIGHT_X} y={y + 4} textAnchor="end" fontWeight={600}>
                  100%
                </text>
                {l.het && (
                  <text x={20} y={y + ROW + 2} fill={MUTED} fontSize={11}>
                    {l.het}
                  </text>
                )}
              </g>
            )
          const s = l.s
          const cells = dataCells(analysis.measure, rowsById.get(s.id), fmt)
          const size = s.weight ? 4 + 8 * Math.sqrt(s.weight / maxW) : 0
          return (
            <g key={i}>
              <text x={8} y={y + 4}>
                {s.label.length > 30 ? s.label.slice(0, 29) + '…' : s.label}
              </text>
              {cells && (
                <>
                  <text x={220} y={y + 4} fill={MUTED}>
                    {cells[0]}
                  </text>
                  <text x={330} y={y + 4} fill={MUTED}>
                    {cells[1]}
                  </text>
                </>
              )}
              {s.estimate != null && s.lower != null && s.upper != null ? (
                <>
                  <line
                    x1={scale.x(scale.clamp(s.lower))}
                    x2={scale.x(scale.clamp(s.upper))}
                    y1={y}
                    y2={y}
                    stroke={INK}
                  />
                  <rect
                    x={scale.x(scale.clamp(s.estimate)) - size / 2}
                    y={y - size / 2}
                    width={size}
                    height={size}
                    fill="#0f766e"
                  />
                  <text x={EST_X} y={y + 4}>
                    {fmt(s.estimate)} [{fmt(s.lower)}; {fmt(s.upper)}]
                  </text>
                  <text x={WEIGHT_X} y={y + 4} textAnchor="end" fill={MUTED}>
                    {s.weight != null ? `${fmt(s.weight, 1)}%` : ''}
                  </text>
                </>
              ) : (
                <text x={EST_X} y={y + 4} fill={MUTED}>
                  {t(`meta.skipped_${s.skipped ?? 'missing'}`)}
                </text>
              )}
            </g>
          )
        })}
        <line x1={PLOT_X} x2={PLOT_X + PLOT_W} y1={axisY} y2={axisY} stroke={INK} />
        {scale.ticks.map((v) => (
          <g key={v}>
            <line x1={scale.x(v)} x2={scale.x(v)} y1={axisY} y2={axisY + 4} stroke={INK} />
            <text x={scale.x(v)} y={axisY + 16} textAnchor="middle" fontSize={11}>
              {v.toLocaleString()}
            </text>
          </g>
        ))}
        {(leftLabel || rightLabel) && (
          <>
            <text x={scale.x(scale.nullValue) - 6} y={axisY + 32} textAnchor="end" fontSize={11} fill={MUTED}>
              {leftLabel ? t('meta.favours', { group: leftLabel }) : ''}
            </text>
            <text x={scale.x(scale.nullValue) + 6} y={axisY + 32} fontSize={11} fill={MUTED}>
              {rightLabel ? t('meta.favours', { group: rightLabel }) : ''}
            </text>
          </>
        )}
        {footer.map((f, i) => (
          <text key={i} x={8} y={axisY + 52 + i * 16} fontSize={11} fill={MUTED}>
            {f}
          </text>
        ))}
      </g>
    </svg>
  )
}

export function FunnelPlot({ result, ref }: { result: MetaResult; ref?: Ref<SVGSVGElement> }) {
  const { t } = useTranslation()
  const pts = result.studies.filter((s) => s.yi != null && s.se != null)
  const p = result.pooled
  if (!p || pts.length < 3) return null
  const W = 520
  const H = 380
  const L = 56
  const R = 16
  const T = 16
  const B = 48
  const center = result.log_scale ? Math.log(p.estimate) : p.estimate
  const maxSe = Math.max(...pts.map((s) => s.se!)) * 1.1
  const spread = Math.max(...pts.map((s) => Math.abs(s.yi! - center)), 1.96 * maxSe) * 1.1
  const x = (v: number) => L + ((v - (center - spread)) / (2 * spread)) * (W - L - R)
  const y = (se: number) => T + (se / maxSe) * (H - T - B)
  const xt = linearTicks(center - spread, center + spread, 6)
  const yt = linearTicks(0, maxSe, 5)
  const label = (v: number) => (result.log_scale ? Math.exp(v) : v).toLocaleString(undefined, { maximumFractionDigits: 2 })
  return (
    <svg ref={ref} xmlns="http://www.w3.org/2000/svg" viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label={t('meta.funnel')}>
      <rect width={W} height={H} fill="#fff" />
      <g fontFamily={FONT} fontSize={11} fill={INK}>
        <polygon
          points={`${x(center)},${y(0)} ${x(center - 1.96 * maxSe)},${y(maxSe)} ${x(center + 1.96 * maxSe)},${y(maxSe)}`}
          fill="#f5f5f4"
          stroke="#a8a29e"
          strokeDasharray="4 3"
        />
        <line x1={x(center)} x2={x(center)} y1={y(0)} y2={y(maxSe)} stroke={MUTED} />
        {pts.map((s) => (
          <circle key={s.id} cx={x(s.yi!)} cy={y(s.se!)} r={4} fill="#0f766e" fillOpacity={0.8}>
            <title>{s.label}</title>
          </circle>
        ))}
        <line x1={L} x2={W - R} y1={H - B} y2={H - B} stroke={INK} />
        <line x1={L} x2={L} y1={T} y2={H - B} stroke={INK} />
        {xt.map((v) => (
          <text key={v} x={x(v)} y={H - B + 16} textAnchor="middle">
            {label(v)}
          </text>
        ))}
        {yt.map((v) => (
          <text key={v} x={L - 6} y={y(v) + 4} textAnchor="end">
            {v.toLocaleString(undefined, { maximumFractionDigits: 2 })}
          </text>
        ))}
        <text x={(L + W - R) / 2} y={H - 10} textAnchor="middle" fill={MUTED}>
          {t(`meta.measure_short_${result.measure}`)}
          {result.log_scale ? ` (${t('meta.log_scale')})` : ''}
        </text>
        <text transform={`translate(14 ${(T + H - B) / 2}) rotate(-90)`} textAnchor="middle" fill={MUTED}>
          {t('meta.standard_error')}
        </text>
      </g>
    </svg>
  )
}
