import type { TFunction } from 'i18next'

export interface Tab {
  to: string
  label: string
  end?: boolean
  badge?: number
}

/** As abas do projeto: etapas do trabalho e itens de preparo (protocolo, IA, equipe). */
export function projectTabs(t: TFunction, canManage: boolean, pendingGroups: number) {
  const workflow: Tab[] = [
    { to: '', label: t('tabs.overview'), end: true },
    { to: 'referencias', label: t('tabs.records') },
    ...(canManage ? [{ to: 'importar', label: t('tabs.import') }] : []),
    { to: 'duplicatas', label: t('tabs.duplicates'), badge: pendingGroups },
    { to: 'triagem', label: t('tabs.screening') },
    { to: 'extracao', label: t('tabs.extraction') },
    { to: 'sintese', label: t('tabs.synthesis') },
    { to: 'relatorio', label: t('tabs.report') },
  ]
  const setup: Tab[] = [
    { to: 'protocolo', label: t('tabs.protocol') },
    { to: 'ia', label: t('tabs.ai') },
    { to: 'conversa', label: t('tabs.corpus') },
    { to: 'membros', label: t('tabs.members') },
    ...(canManage ? [{ to: 'configuracoes', label: t('tabs.settings') }] : []),
  ]
  return { workflow, setup }
}
