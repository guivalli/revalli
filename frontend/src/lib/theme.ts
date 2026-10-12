import { useSyncExternalStore } from 'react'

export type ThemeChoice = 'system' | 'light' | 'dark'

const KEY = 'revalli.theme'
const listeners = new Set<() => void>()

function stored(): ThemeChoice {
  try {
    const v = localStorage.getItem(KEY)
    return v === 'light' || v === 'dark' ? v : 'system'
  } catch {
    return 'system'
  }
}

let choice: ThemeChoice = stored()

function prefersDark(): boolean {
  return typeof matchMedia === 'function' && matchMedia('(prefers-color-scheme: dark)').matches
}

/** Aplica a escolha na raiz do documento: a classe `dark` liga as variantes escuras. */
function apply() {
  const dark = choice === 'dark' || (choice === 'system' && prefersDark())
  document.documentElement.classList.toggle('dark', dark)
}

export function setTheme(next: ThemeChoice) {
  choice = next
  try {
    if (next === 'system') localStorage.removeItem(KEY)
    else localStorage.setItem(KEY, next)
  } catch {
    // Sem armazenamento (janela privada): vale só nesta sessão
  }
  apply()
  listeners.forEach((l) => l())
}

/** Chamado uma vez antes de renderizar, para a tela já abrir no tema certo. */
export function initTheme() {
  apply()
  if (typeof matchMedia === 'function') {
    matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
      if (choice === 'system') apply()
    })
  }
}

export function useTheme(): [ThemeChoice, (c: ThemeChoice) => void] {
  const current = useSyncExternalStore(
    (cb) => {
      listeners.add(cb)
      return () => listeners.delete(cb)
    },
    () => choice,
  )
  return [current, setTheme]
}
