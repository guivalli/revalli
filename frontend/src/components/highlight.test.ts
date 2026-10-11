import { describe, expect, it } from 'vitest'
import { highlight } from './highlight'

describe('highlight', () => {
  it('marca termos de inclusão e exclusão sem diferenciar maiúsculas', () => {
    const segs = highlight('A Randomized trial in rats.', ['random*'], ['rats'])
    expect(segs).toEqual([
      { text: 'A ', kind: null },
      { text: 'Randomized', kind: 'include' },
      { text: ' trial in ', kind: null },
      { text: 'rats', kind: 'exclude' },
      { text: '.', kind: null },
    ])
  })

  it('respeita fronteiras de palavras com acento', () => {
    const segs = highlight('idosos e idosas; não idosossss', ['idos*s'], [])
    expect(segs.filter((s) => s.kind).map((s) => s.text)).toEqual(['idosos', 'idosas', 'idosossss'])
    expect(highlight('ansiedade', ['ansia'], [])).toEqual([{ text: 'ansiedade', kind: null }])
  })

  it('prefere o termo mais longo e escapa caracteres especiais', () => {
    const segs = highlight('ensaio clínico (fase 2)', ['ensaio', 'ensaio clínico', '(fase 2)'], [])
    expect(segs.filter((s) => s.kind).map((s) => s.text)).toEqual(['ensaio clínico', '(fase 2)'])
  })

  it('sem termos devolve o texto inteiro', () => {
    expect(highlight('abc', [], [])).toEqual([{ text: 'abc', kind: null }])
  })
})
