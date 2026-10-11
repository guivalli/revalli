import { describe, expect, it } from 'vitest'
import { certaintyOf, certaintySymbols, csvCell } from './grade'

describe('certaintyOf', () => {
  it('parte de alta em ECR e rebaixa', () => {
    expect(certaintyOf({ design: 'rct', domains: {} })).toBe('high')
    expect(certaintyOf({ design: 'rct', domains: { imprecision: { rating: -1, reason: '' } } })).toBe('moderate')
    expect(
      certaintyOf({ design: 'rct', domains: { risk_of_bias: { rating: -2, reason: '' }, inconsistency: { rating: -2, reason: '' } } }),
    ).toBe('very_low')
  })
  it('eleva estudos observacionais, sem passar de alta', () => {
    expect(certaintyOf({ design: 'observational', domains: {} })).toBe('low')
    expect(certaintyOf({ design: 'observational', domains: { large_effect: { rating: 2, reason: '' } } })).toBe('high')
    expect(certaintyOf({ design: 'rct', domains: { large_effect: { rating: 2, reason: '' } } })).toBe('high')
  })
  it('desenha os símbolos', () => {
    expect(certaintySymbols('moderate')).toBe('⊕⊕⊕◯')
  })
  it('escapa células do CSV', () => {
    expect(csvCell('a, "b"')).toBe('"a, ""b"""')
    expect(csvCell(null)).toBe('')
  })
})
