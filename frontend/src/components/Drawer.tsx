import { useEffect, useRef, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

/** Painel que desliza da lateral por cima da página, sem trocar de rota. Fecha com Esc, com
 * clique fora ou pelo botão; o foco vai para o painel ao abrir e volta ao botão que abriu. */
export function Drawer({
  open,
  onClose,
  side = 'left',
  title,
  children,
}: {
  open: boolean
  onClose: () => void
  side?: 'left' | 'right'
  title: string
  children: ReactNode
}) {
  const { t } = useTranslation()
  const panel = useRef<HTMLDivElement>(null)
  const opener = useRef<Element | null>(null)

  useEffect(() => {
    if (!open) return
    opener.current = document.activeElement
    panel.current?.focus()
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('keydown', onKey)
      if (opener.current instanceof HTMLElement) opener.current.focus()
    }
  }, [open, onClose])

  const edge = side === 'left' ? 'left-0 border-r' : 'right-0 border-l'
  const hidden = side === 'left' ? '-translate-x-full' : 'translate-x-full'
  return (
    <>
      <div
        aria-hidden
        onClick={onClose}
        className={`fixed inset-0 z-40 bg-stone-900/40 transition-opacity duration-200 ${
          open ? 'opacity-100' : 'pointer-events-none opacity-0'
        }`}
      />
      <div
        ref={panel}
        tabIndex={-1}
        role="dialog"
        aria-modal={open}
        aria-label={title}
        className={`fixed inset-y-0 z-50 flex w-80 max-w-[88vw] flex-col border-stone-200 bg-white shadow-xl outline-none transition-[transform,visibility] duration-200 dark:border-stone-800 dark:bg-stone-900 ${edge} ${
          open ? 'visible translate-x-0' : `invisible ${hidden}`
        }`}
      >
        <div className="flex items-center justify-between border-b border-stone-200 px-4 py-3 dark:border-stone-800">
          <h2 className="font-semibold">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label={t('app.close')}
            className="rounded p-1 text-stone-500 hover:bg-stone-100 dark:hover:bg-stone-800"
          >
            ✕
          </button>
        </div>
        <div className="flex-1 overflow-y-auto">{children}</div>
      </div>
    </>
  )
}
