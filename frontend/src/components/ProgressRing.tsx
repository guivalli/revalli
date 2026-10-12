export interface RingSegment {
  value: number
  color: string
  label: string
}

const SIZE = 132
const STROKE = 14
const RADIUS = (SIZE - STROKE) / 2
const CIRCUMFERENCE = 2 * Math.PI * RADIUS
// Espaço entre segmentos vizinhos, na cor da superfície
const GAP = 2

/** Anel de progresso: um arco por segmento, em ordem, sobre uma trilha neutra. O texto do
 * centro e a legenda (fora do SVG) dizem os números; a cor nunca é a única informação. */
export function ProgressRing({
  segments,
  total,
  center,
  caption,
}: {
  segments: RingSegment[]
  total: number
  center: string
  caption: string
}) {
  const drawn = segments.filter((s) => s.value > 0)
  let offset = 0
  return (
    <svg
      role="img"
      aria-label={caption}
      viewBox={`0 0 ${SIZE} ${SIZE}`}
      className="size-32 shrink-0 text-stone-200 dark:text-stone-800"
    >
      <g transform={`rotate(-90 ${SIZE / 2} ${SIZE / 2})`}>
      <circle
        cx={SIZE / 2}
        cy={SIZE / 2}
        r={RADIUS}
        fill="none"
        stroke="currentColor"
        strokeWidth={STROKE}
      />
      {total > 0 &&
        drawn.map((s) => {
          const length = (s.value / total) * CIRCUMFERENCE
          const start = offset
          offset += length
          const visible = drawn.length > 1 ? Math.max(length - GAP, 0.5) : length
          return (
            <circle
              key={s.label}
              cx={SIZE / 2}
              cy={SIZE / 2}
              r={RADIUS}
              fill="none"
              stroke={s.color}
              strokeWidth={STROKE}
              strokeDasharray={`${visible} ${CIRCUMFERENCE - visible}`}
              strokeDashoffset={-start}
            />
          )
        })}
      </g>
      <text
        x={SIZE / 2}
        y={SIZE / 2}
        textAnchor="middle"
        dominantBaseline="central"
        className="fill-stone-900 text-2xl font-semibold dark:fill-stone-100"
      >
        {center}
      </text>
    </svg>
  )
}
