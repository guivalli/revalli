import { describe, expect, it } from 'vitest'
import en from './en.json'
import ptBR from './pt-BR.json'

function keys(obj: object, prefix = ''): string[] {
  return Object.entries(obj).flatMap(([k, v]) =>
    typeof v === 'object' && v !== null ? keys(v, `${prefix}${k}.`) : [`${prefix}${k}`],
  )
}

describe('traduções', () => {
  it('pt-BR e en têm as mesmas chaves', () => {
    expect(keys(en).sort()).toEqual(keys(ptBR).sort())
  })
})
