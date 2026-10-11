"""Divide o texto de uma página em trechos de tamanho parecido, com sobreposição.

Os trechos nunca atravessam páginas, para que a página citada seja sempre exata."""

SIZE = 1100
OVERLAP = 150
MIN_CHARS = 40


def split_text(text: str, size: int = SIZE, overlap: int = OVERLAP) -> list[str]:
    flat = " ".join(text.split())
    if len(flat) <= size:
        return [flat] if flat else []
    out: list[str] = []
    start = 0
    while start < len(flat):
        end = min(start + size, len(flat))
        if end < len(flat):
            # Prefere terminar numa frase; senão, numa palavra
            window = flat[start:end]
            cut = max(window.rfind(". "), window.rfind("? "), window.rfind("! "))
            if cut < size * 0.6:
                cut = window.rfind(" ")
            if cut > size * 0.4:
                end = start + cut + 1
        piece = flat[start:end].strip()
        if piece:
            out.append(piece)
        if end >= len(flat):
            break
        nxt = max(end - overlap, start + 1)
        # Recomeça no começo de uma palavra
        space = flat.find(" ", nxt)
        start = space + 1 if 0 <= space < end else nxt
    # Sobras minúsculas (número de página, rodapé) não valem um trecho
    if len(out) > 1 and len(out[-1]) < MIN_CHARS:
        out.pop()
    return out
