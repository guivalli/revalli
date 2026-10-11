import type { Ref } from 'react'
import { useTranslation } from 'react-i18next'
import type { RobSummaryT } from '../api/types'

// Cores e símbolos usuais dos gráficos de risco de viés
const LEVELS: Record<string, { color: string; symbol: string }> = {
  low: { color: '#16a34a', symbol: '+' },
  some: { color: '#eab308', symbol: '−' },
  moderate: { color: '#eab308', symbol: '−' },
  high: { color: '#dc2626', symbol: '×' },
  serious: { color: '#dc2626', symbol: '×' },
  critical: { color: '#7f1d1d', symbol: '!' },
  ni: { color: '#9ca3af', symbol: '?' },
}
const FONT = 'Inter, Helvetica, Arial, sans-serif'
const INK = '#1c1917'

function cut(s: string, n: number) {
  return s.length > n ? s.slice(0, n - 1) + '…' : s
}

function short(d: { domain: string }, i: number, total: number, overall: string) {
  return d.domain === 'overall' || i === total - 1 ? overall : d.domain.toUpperCase()
}

function Legend({ data, y, x }: { data: RobSummaryT; y: number; x: number }) {
  const { t } = useTranslation()
  return (
    <g fontFamily={FONT} fontSize={12} fill={INK}>
      {data.scale.map((lv, i) => {
        const l = LEVELS[lv]
        // Largura aproximada de cada item, para os rótulos não se sobreporem
        const offset = data.scale.slice(0, i).reduce((acc, k) => acc + t(`rob.level_${k}`).length * 7 + 44, 0)
        return (
          <g key={lv} transform={`translate(${x + offset}, ${y})`}>
            <circle cx={8} cy={0} r={8} fill={l?.color ?? '#ccc'} />
            <text x={8} y={4} textAnchor="middle" fill="#fff" fontWeight={700} fontSize={12}>
              {l?.symbol}
            </text>
            <text x={22} y={4}>
              {t(`rob.level_${lv}`)}
            </text>
          </g>
        )
      })}
    </g>
  )
}

export function TrafficLight({ data, ref }: { data: RobSummaryT; ref?: Ref<SVGSVGElement> }) {
  const { t } = useTranslation()
  const labelW = 230
  const colW = 56
  const rowH = 30
  const top = 40
  const n = data.domains.length
  const tableH = data.rows.length * rowH
  const legendY = top + tableH + 30
  const domainsY = legendY + 30
  const width = Math.max(labelW + n * colW + 20, 620)
  const height = domainsY + n * 18 + 16
  return (
    <svg ref={ref} xmlns="http://www.w3.org/2000/svg" viewBox={`0 0 ${width} ${height}`} width="100%" role="img" aria-label={t('rob.traffic_light')}>
      <rect width={width} height={height} fill="#fff" />
      <g fontFamily={FONT} fontSize={13} fill={INK}>
        {data.domains.map((d, i) => (
          <text key={d.id} x={labelW + i * colW + colW / 2} y={top - 14} textAnchor="middle" fontWeight={600}>
            {short(d, i, n, t('rob.overall_short'))}
          </text>
        ))}
        {data.rows.map((r, ri) => {
          const y = top + ri * rowH
          return (
            <g key={r.record_id}>
              <rect x={0} y={y} width={width} height={rowH} fill={ri % 2 ? '#fafaf9' : '#fff'} />
              <text x={8} y={y + rowH / 2 + 4}>
                {cut(r.label, 30)}
              </text>
              {data.domains.map((d, i) => {
                const lv = r.judgements[d.id]
                const l = lv ? LEVELS[lv] : null
                const cx = labelW + i * colW + colW / 2
                return l ? (
                  <g key={d.id}>
                    <circle cx={cx} cy={y + rowH / 2} r={11} fill={l.color} />
                    <text x={cx} y={y + rowH / 2 + 5} textAnchor="middle" fill="#fff" fontWeight={700} fontSize={14}>
                      {l.symbol}
                    </text>
                  </g>
                ) : (
                  <circle key={d.id} cx={cx} cy={y + rowH / 2} r={11} fill="none" stroke="#d6d3d1" strokeDasharray="3 3" />
                )
              })}
            </g>
          )
        })}
      </g>
      <Legend data={data} x={8} y={legendY} />
      <g fontFamily={FONT} fontSize={11} fill="#57534e">
        {data.domains.map((d, i) => (
          <text key={d.id} x={8} y={domainsY + i * 18}>
            {short(d, i, n, t('rob.overall_short'))}: {d.label.replace(/^D\d+\.\s*/, '')}
          </text>
        ))}
      </g>
    </svg>
  )
}

export function SummaryPlot({ data, ref }: { data: RobSummaryT; ref?: Ref<SVGSVGElement> }) {
  const { t } = useTranslation()
  const labelW = 260
  const barW = 420
  const rowH = 30
  const top = 16
  const n = data.domains.length
  const width = labelW + barW + 30
  const legendY = top + n * rowH + 36
  const height = legendY + 20
  return (
    <svg ref={ref} xmlns="http://www.w3.org/2000/svg" viewBox={`0 0 ${width} ${height}`} width="100%" role="img" aria-label={t('rob.summary')}>
      <rect width={width} height={height} fill="#fff" />
      <g fontFamily={FONT} fontSize={12} fill={INK}>
        {data.domains.map((d, i) => {
          const y = top + i * rowH
          const counts = data.scale.map((lv) => data.rows.filter((r) => r.judgements[d.id] === lv).length)
          const total = counts.reduce((a, b) => a + b, 0)
          let x = labelW
          return (
            <g key={d.id}>
              <text x={labelW - 8} y={y + rowH / 2 + 4} textAnchor="end">
                {cut(d.label.replace(/^D(\d+)\.\s*/, 'D$1 '), 40)}
              </text>
              {total === 0 && <rect x={labelW} y={y + 5} width={barW} height={rowH - 10} fill="#f5f5f4" />}
              {data.scale.map((lv, k) => {
                const w = total ? (counts[k] / total) * barW : 0
                const rect = (
                  <g key={lv}>
                    <rect x={x} y={y + 5} width={w} height={rowH - 10} fill={LEVELS[lv]?.color ?? '#ccc'} />
                    {w > 34 && (
                      <text x={x + w / 2} y={y + rowH / 2 + 4} textAnchor="middle" fill="#fff" fontWeight={600}>
                        {Math.round((counts[k] / total) * 100)}%
                      </text>
                    )}
                  </g>
                )
                x += w
                return rect
              })}
            </g>
          )
        })}
        {[0, 25, 50, 75, 100].map((p) => (
          <text key={p} x={labelW + (p / 100) * barW} y={top + n * rowH + 14} textAnchor="middle" fill="#78716c" fontSize={11}>
            {p}%
          </text>
        ))}
      </g>
      <Legend data={data} x={labelW} y={legendY} />
    </svg>
  )
}
