export interface Segment {
  text: string
  kind: 'include' | 'exclude' | null
}

const escape = (s: string) => s.replace(/[.+?^${}()|[\]\\]/g, '\\$&')

/** Monta a expressão de um termo: "random*" casa com random, randomized, randomised... */
function termPattern(term: string): string {
  const t = term.trim()
  const body = escape(t).replace(/\*/g, '[\\p{L}\\p{N}]*')
  // \b não entende acentos; usamos fronteiras baseadas em letras Unicode
  return `(?<![\\p{L}\\p{N}])${body}(?![\\p{L}\\p{N}])`
}

/** Divide o texto em pedaços marcados com os termos de inclusão e exclusão. */
export function highlight(text: string, include: string[], exclude: string[]): Segment[] {
  const terms = [
    ...include.filter((t) => t.trim()).map((t) => ({ t, kind: 'include' as const })),
    ...exclude.filter((t) => t.trim()).map((t) => ({ t, kind: 'exclude' as const })),
  ]
  if (!text || terms.length === 0) return [{ text, kind: null }]
  // Termos mais longos primeiro, para "ensaio clínico" ganhar de "ensaio"
  terms.sort((a, b) => b.t.length - a.t.length)
  const re = new RegExp(terms.map(({ t }) => `(${termPattern(t)})`).join('|'), 'giu')
  const out: Segment[] = []
  let last = 0
  for (const m of text.matchAll(re)) {
    const idx = m.index ?? 0
    if (m[0].length === 0) continue
    if (idx > last) out.push({ text: text.slice(last, idx), kind: null })
    const group = m.slice(1).findIndex((g) => g !== undefined)
    out.push({ text: m[0], kind: terms[group].kind })
    last = idx + m[0].length
  }
  if (last < text.length) out.push({ text: text.slice(last), kind: null })
  return out
}
