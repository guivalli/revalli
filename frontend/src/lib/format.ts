import { useTranslation } from 'react-i18next'

/** Número no formato do idioma da interface, com casas decimais fixas. */
export function useFmt() {
  const { i18n } = useTranslation()
  return (v: number | null | undefined, digits = 2) =>
    v == null || !Number.isFinite(v)
      ? '–'
      : v.toLocaleString(i18n.language, { minimumFractionDigits: digits, maximumFractionDigits: digits })
}

/** Valor p com três casas, ou "< 0,001". */
export function useFmtP() {
  const fmt = useFmt()
  return (p: number | null | undefined) => (p == null ? '–' : p < 0.001 ? `< ${fmt(0.001, 3)}` : fmt(p, 3))
}
