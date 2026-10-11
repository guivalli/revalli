import type { Code } from '../api/types'

export function CodeDot({ code }: { code: Pick<Code, 'color'> }) {
  return (
    <span
      aria-hidden
      className="inline-block size-2.5 shrink-0 rounded-full"
      style={{ background: code.color || '#a8a29e' }}
    />
  )
}
