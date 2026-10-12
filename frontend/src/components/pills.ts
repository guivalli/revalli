/** Barra de abas em pílulas: o mesmo visual para a navegação do projeto e as internas. */
export const pillBar = 'inline-flex items-center gap-1 rounded-lg bg-stone-200/70 p-1 dark:bg-stone-900'

export const pillItem = (active: boolean) =>
  `flex items-center gap-2 whitespace-nowrap rounded-md px-3 py-1.5 text-sm transition ${
    active
      ? 'bg-white font-medium text-stone-900 shadow-sm dark:bg-stone-800 dark:text-stone-100'
      : 'text-stone-600 hover:bg-white/70 hover:text-stone-900 dark:text-stone-400 dark:hover:bg-stone-800/60 dark:hover:text-stone-100'
  }`
