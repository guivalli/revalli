export function download(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  URL.revokeObjectURL(url)
}

export function svgText(svg: SVGSVGElement) {
  return '<?xml version="1.0" encoding="UTF-8"?>\n' + new XMLSerializer().serializeToString(svg)
}

export async function svgToPng(svg: SVGSVGElement): Promise<Blob | null> {
  const box = svg.viewBox.baseVal
  const scale = 2
  const img = new Image()
  img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svgText(svg))
  await img.decode()
  const canvas = document.createElement('canvas')
  canvas.width = box.width * scale
  canvas.height = box.height * scale
  const ctx = canvas.getContext('2d')
  if (!ctx) return null
  ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
  return new Promise((resolve) => canvas.toBlob(resolve, 'image/png'))
}

export function saveSvg(svg: SVGSVGElement | null, name: string) {
  if (svg) download(new Blob([svgText(svg)], { type: 'image/svg+xml' }), `${name}.svg`)
}

export async function savePng(svg: SVGSVGElement | null, name: string) {
  if (!svg) return
  const blob = await svgToPng(svg)
  if (blob) download(blob, `${name}.png`)
}
