import { useMemo } from 'react'
import { highlight } from './highlight'

export function HighlightedText({
  text,
  include,
  exclude,
}: {
  text: string
  include: string[]
  exclude: string[]
}) {
  const segments = useMemo(() => highlight(text, include, exclude), [text, include, exclude])
  return (
    <>
      {segments.map((s, i) =>
        s.kind === 'include' ? (
          <mark key={i} className="rounded bg-green-200 px-0.5 text-inherit dark:bg-green-900">
            {s.text}
          </mark>
        ) : s.kind === 'exclude' ? (
          <mark key={i} className="rounded bg-red-200 px-0.5 text-inherit dark:bg-red-900">
            {s.text}
          </mark>
        ) : (
          <span key={i}>{s.text}</span>
        ),
      )}
    </>
  )
}
