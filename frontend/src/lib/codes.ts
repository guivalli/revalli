import type { Code } from '../api/types'

/** Códigos em ordem de árvore, com a profundidade de cada um. */
export function flattenCodes(codes: Code[]): { code: Code; depth: number }[] {
  const children = new Map<string | null, Code[]>()
  for (const c of codes) {
    const list = children.get(c.parent_id) ?? []
    list.push(c)
    children.set(c.parent_id, list)
  }
  for (const list of children.values())
    list.sort((a, b) => a.position - b.position || a.name.localeCompare(b.name))
  const out: { code: Code; depth: number }[] = []
  const walk = (parent: string | null, depth: number) => {
    for (const c of children.get(parent) ?? []) {
      out.push({ code: c, depth })
      walk(c.id, depth + 1)
    }
  }
  walk(null, 0)
  return out
}

/** O código e todos os subcódigos dele. */
export function codeSubtree(codes: Code[], id: string): Set<string> {
  const out = new Set([id])
  let grew = true
  while (grew) {
    grew = false
    for (const c of codes)
      if (c.parent_id && out.has(c.parent_id) && !out.has(c.id)) {
        out.add(c.id)
        grew = true
      }
  }
  return out
}

export const CODE_COLORS = ['#0f766e', '#2563eb', '#7c3aed', '#db2777', '#ea580c', '#ca8a04', '#16a34a', '#57534e']
