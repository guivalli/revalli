import { useOutletContext } from 'react-router-dom'
import type { Project } from '../../api/types'

export interface ProjectContext {
  project: Project
  canManage: boolean
}

export const useProjectContext = () => useOutletContext<ProjectContext>()
