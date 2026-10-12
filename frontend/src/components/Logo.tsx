/** Marca do ReValli. Cada variante tem versão clara e escura; a escura aparece com a classe
 * `dark` na raiz (ver lib/theme.ts), por isso são duas imagens e o CSS escolhe uma. */
const SOURCES = {
  icon: { light: '/brand/icon.png', dark: '/brand/icon-dark.png', ratio: 1 },
  wordmark: { light: '/brand/wordmark.png', dark: '/brand/wordmark-dark.png', ratio: 3.28 },
  stacked: { light: '/brand/stacked.png', dark: '/brand/stacked-dark.png', ratio: 1.11 },
} as const

export function Logo({
  variant,
  height,
  alt = 'ReValli',
  className = '',
}: {
  variant: keyof typeof SOURCES
  height: number
  alt?: string
  className?: string
}) {
  const s = SOURCES[variant]
  const size = { height, width: Math.round(height * s.ratio) }
  // O invólucro cuida do tamanho de tela e as imagens, do tema: assim as classes não brigam
  return (
    <span className={className}>
      <img src={s.light} alt={alt} {...size} className="dark:hidden" />
      <img src={s.dark} alt={alt} {...size} className="hidden dark:block" />
    </span>
  )
}
