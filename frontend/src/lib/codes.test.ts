import { describe, expect, it } from 'vitest'
import type { Code } from '../api/types'
import { codeSubtree, flattenCodes } from './codes'

const c = (id: string, parent: string | null, position = 0): Code => ({
  id,
  parent_id: parent,
  name: id,
  description: '',
  color: '',
  position,
  excerpts: 0,
})

describe('code tree', () => {
  const codes = [c('b', null, 1), c('a', null, 0), c('a2', 'a', 1), c('a1', 'a', 0), c('x', 'a1')]
  it('flattens in tree order with depth', () => {
    expect(flattenCodes(codes).map((r) => `${r.code.id}:${r.depth}`)).toEqual(['a:0', 'a1:1', 'x:2', 'a2:1', 'b:0'])
  })
  it('collects descendants', () => {
    expect([...codeSubtree(codes, 'a')].sort()).toEqual(['a', 'a1', 'a2', 'x'])
    expect([...codeSubtree(codes, 'b')]).toEqual(['b'])
  })
})
