// Ordem e seções dos itens dos checklists de relato. Os textos ficam no i18n (checklist_items).
export const CHECKLIST_SECTIONS = {
  prisma2020: {"title": ["1"], "abstract": ["2"], "introduction": ["3", "4"], "methods": ["5", "6", "7", "8", "9", "10a", "10b", "11", "12", "13a", "13b", "13c", "13d", "13e", "13f", "14", "15"], "results": ["16a", "16b", "17", "18", "19", "20a", "20b", "20c", "20d", "21", "22"], "discussion": ["23a", "23b", "23c", "23d"], "other": ["24a", "24b", "24c", "25", "26", "27"]},
  prisma_scr: {"title": ["1"], "abstract": ["2"], "introduction": ["3", "4"], "methods": ["5", "6", "7", "8", "9", "10", "11", "12", "13"], "results": ["14", "15", "16", "17", "18"], "discussion": ["19", "20", "21"], "other": ["22"]},
} as const satisfies Record<string, Record<string, readonly string[]>>

export type ChecklistKind = keyof typeof CHECKLIST_SECTIONS
