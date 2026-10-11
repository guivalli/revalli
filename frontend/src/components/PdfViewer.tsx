import { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { PDFDocumentProxy } from 'pdfjs-dist'
import './pdf-text-layer.css'
import { highlight } from './highlight'

// O pdf.js é grande: só é baixado quando um PDF é aberto. A versão "legacy" traz os
// polyfills de recursos recentes do JavaScript que navegadores comuns ainda não têm.
async function loadPdfjs() {
  const [pdfjs, worker] = await Promise.all([
    import('pdfjs-dist/legacy/build/pdf.mjs'),
    import('pdfjs-dist/legacy/build/pdf.worker.min.mjs?url'),
  ])
  pdfjs.GlobalWorkerOptions.workerSrc = worker.default
  return pdfjs
}

const MARK = {
  include: 'background: rgb(16 185 129 / 0.35)',
  exclude: 'background: rgb(239 68 68 / 0.35)',
}

/** Marca os termos dentro dos trechos da camada de texto (que é transparente sobre o desenho). */
function markTerms(container: HTMLElement, include: string[], exclude: string[]): number {
  let hits = 0
  for (const span of container.querySelectorAll<HTMLSpanElement>('span')) {
    if (span.childElementCount > 0) continue
    const text = span.textContent ?? ''
    const parts = highlight(text, include, exclude)
    if (parts.every((p) => !p.kind)) continue
    span.textContent = ''
    for (const p of parts) {
      if (!p.kind) {
        span.append(p.text)
        continue
      }
      const mark = document.createElement('mark')
      mark.textContent = p.text
      mark.setAttribute('style', `${MARK[p.kind]}; color: transparent; border-radius: 2px`)
      span.append(mark)
      hits++
    }
  }
  return hits
}

const norm = (s: string) => s.toLowerCase().replace(/\s+/g, ' ').trim()

/** Destaca os trechos da camada de texto que formam a citação. Devolve o primeiro, para rolar
 * até ele. Procura a citação inteira e, se não achar, o começo dela. */
function markQuote(container: HTMLElement, quote: string): HTMLElement | null {
  const spans = [...container.querySelectorAll<HTMLSpanElement>('span:not(.markedContent)')].filter(
    (s) => s.childElementCount === 0 || s.querySelector('mark'),
  )
  let text = ''
  const starts: number[] = []
  for (const s of spans) {
    starts.push(text.length)
    text += norm(s.textContent ?? '') + ' '
  }
  const q = norm(quote)
  let at = text.indexOf(q)
  let len = q.length
  if (at < 0 && q.length > 40) {
    at = text.indexOf(q.slice(0, 40))
    len = 40
  }
  if (at < 0) return null
  let first: HTMLElement | null = null
  spans.forEach((s, i) => {
    const end = (starts[i + 1] ?? text.length) - 1
    if (starts[i] < at + len && end > at) {
      s.style.background = 'rgb(250 204 21 / 0.45)'
      s.style.borderRadius = '2px'
      first ??= s
    }
  })
  return first
}

export interface PdfFocus {
  page: number
  text: string
}

/** Texto selecionado com o mouse e a página onde a seleção começa. */
export interface PdfSelection {
  page: number | null
  text: string
}

function readSelection(): PdfSelection | null {
  const sel = window.getSelection()
  const text = sel?.toString().replace(/\s+/g, ' ').trim() ?? ''
  if (!sel || text.length < 3) return null
  const node = sel.anchorNode
  const el = (node instanceof Element ? node : node?.parentElement)?.closest('[data-page]')
  return { page: el ? Number(el.getAttribute('data-page')) : null, text }
}

function Page({
  doc,
  number,
  scale,
  include,
  exclude,
  onHits,
  focus,
}: {
  doc: PDFDocumentProxy
  number: number
  scale: number
  include: string[]
  exclude: string[]
  onHits: (page: number, n: number) => void
  focus?: string
}) {
  const wrap = useRef<HTMLDivElement>(null)
  const canvas = useRef<HTMLCanvasElement>(null)
  const text = useRef<HTMLDivElement>(null)
  const [seen, setVisible] = useState(number <= 2)
  const visible = seen || !!focus
  const [size, setSize] = useState<{ w: number; h: number } | null>(null)

  useEffect(() => {
    let cancelled = false
    void doc.getPage(number).then((page) => {
      if (cancelled) return
      const vp = page.getViewport({ scale })
      setSize({ w: vp.width, h: vp.height })
    })
    return () => {
      cancelled = true
    }
  }, [doc, number, scale])

  useEffect(() => {
    const el = wrap.current
    if (!el || visible) return
    const io = new IntersectionObserver(
      (entries) => entries.some((e) => e.isIntersecting) && setVisible(true),
      { rootMargin: '600px' },
    )
    io.observe(el)
    return () => io.disconnect()
  }, [visible])

  useEffect(() => {
    if (!visible || !canvas.current || !text.current) return
    let cancelled = false
    const textEl = text.current
    const canvasEl = canvas.current
    let task: { cancel: () => void } | null = null
    void (async () => {
      const pdfjs = await loadPdfjs()
      const page = await doc.getPage(number)
      if (cancelled) return
      const vp = page.getViewport({ scale })
      const ratio = window.devicePixelRatio || 1
      canvasEl.width = Math.floor(vp.width * ratio)
      canvasEl.height = Math.floor(vp.height * ratio)
      canvasEl.style.width = `${vp.width}px`
      canvasEl.style.height = `${vp.height}px`
      const render = page.render({
        canvas: canvasEl,
        viewport: vp,
        transform: ratio !== 1 ? [ratio, 0, 0, ratio, 0, 0] : undefined,
      })
      task = render
      await render.promise.catch(() => undefined)
      if (cancelled) return
      textEl.replaceChildren()
      textEl.style.setProperty('--total-scale-factor', String(scale))
      const layer = new pdfjs.TextLayer({
        textContentSource: page.streamTextContent(),
        container: textEl,
        viewport: vp,
      })
      await layer.render()
      if (cancelled) return
      onHits(number, markTerms(textEl, include, exclude))
      if (focus) {
        const el = markQuote(textEl, focus) ?? wrap.current
        el?.scrollIntoView({ block: 'center' })
      }
    })()
    return () => {
      cancelled = true
      task?.cancel()
    }
  }, [visible, doc, number, scale, include, exclude, onHits, focus])

  useEffect(() => {
    if (focus) wrap.current?.scrollIntoView({ block: 'start' })
  }, [focus])

  return (
    <div
      ref={wrap}
      className="relative mx-auto bg-white shadow"
      style={{ width: size?.w ?? 600, height: size?.h ?? 800 }}
      data-page={number}
    >
      <canvas ref={canvas} className="absolute inset-0" />
      <div ref={text} className="textLayer" />
    </div>
  )
}

/** Use com key={url}: trocar de arquivo monta um visualizador novo. */
export function PdfViewer({
  url,
  include,
  exclude,
  focus,
  onSelect,
}: {
  url: string
  include: string[]
  exclude: string[]
  focus?: PdfFocus | null
  onSelect?: (sel: PdfSelection) => void
}) {
  const { t } = useTranslation()
  const [doc, setDoc] = useState<PDFDocumentProxy | null>(null)
  const [error, setError] = useState(false)
  const [scale, setScale] = useState(1)
  const [hits, setHits] = useState<Record<number, number>>({})

  useEffect(() => {
    let cancelled = false
    let loaded: PDFDocumentProxy | null = null
    void loadPdfjs()
      .then((pdfjs) => pdfjs.getDocument({ url, withCredentials: true }).promise)
      .then((d) => {
        loaded = d
        if (cancelled) void d.destroy()
        else setDoc(d)
      })
      .catch(() => !cancelled && setError(true))
    return () => {
      cancelled = true
      void loaded?.destroy()
    }
  }, [url])

  const onHits = useCallback((page: number, n: number) => setHits((h) => ({ ...h, [page]: n })), [])
  const total = Object.values(hits).reduce((a, b) => a + b, 0)

  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-wrap items-center gap-2 border-b border-stone-200 px-3 py-2 text-sm dark:border-stone-800">
        <button
          type="button"
          aria-label={t('pdf.zoom_out')}
          className="rounded px-2 hover:bg-stone-100 dark:hover:bg-stone-800"
          onClick={() => setScale((s) => Math.max(0.6, +(s - 0.2).toFixed(1)))}
        >
          −
        </button>
        <span className="tabular-nums">{Math.round(scale * 100)}%</span>
        <button
          type="button"
          aria-label={t('pdf.zoom_in')}
          className="rounded px-2 hover:bg-stone-100 dark:hover:bg-stone-800"
          onClick={() => setScale((s) => Math.min(3, +(s + 0.2).toFixed(1)))}
        >
          +
        </button>
        {doc && <span className="text-stone-500">{t('pdf.pages', { count: doc.numPages })}</span>}
        {total > 0 && <span className="text-stone-500">{t('pdf.hits', { count: total })}</span>}
        <a href={url} target="_blank" rel="noreferrer" className="ml-auto text-brand-600 hover:underline">
          {t('pdf.open')}
        </a>
      </div>
      <div
        className="flex-1 space-y-4 overflow-auto bg-stone-200 p-4 dark:bg-stone-800"
        onMouseUp={
          onSelect
            ? () => {
                const sel = readSelection()
                if (sel) onSelect(sel)
              }
            : undefined
        }
      >
        {error && <p className="text-sm text-red-700">{t('pdf.error')}</p>}
        {!doc && !error && <p className="text-sm text-stone-500">{t('app.loading')}</p>}
        {doc &&
          Array.from({ length: doc.numPages }, (_, i) => (
            <Page
              key={`${i}-${scale}`}
              doc={doc}
              number={i + 1}
              scale={scale}
              include={include}
              exclude={exclude}
              onHits={onHits}
              focus={focus?.page === i + 1 ? focus.text : undefined}
            />
          ))}
      </div>
    </div>
  )
}
