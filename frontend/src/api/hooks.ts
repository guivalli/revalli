import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError, api } from './client'
import type { InvitationCreated, Member, Project, ReviewType, Role, User } from './types'

export function useSetupStatus() {
  return useQuery({
    queryKey: ['setup'],
    queryFn: () => api.get<{ needs_setup: boolean }>('/setup'),
  })
}

export function useMe() {
  return useQuery({
    queryKey: ['me'],
    queryFn: async () => {
      try {
        return await api.get<User>('/auth/me')
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) return null
        throw e
      }
    },
  })
}

export function useLogout() {
  return useMutation({
    mutationFn: () => api.post<void>('/auth/logout'),
    // Recarrega a página para descartar todo o estado em memória do usuário anterior
    onSuccess: () => window.location.assign('/login'),
  })
}

export function useProjects() {
  return useQuery({ queryKey: ['projects'], queryFn: () => api.get<Project[]>('/projects') })
}

export function useProject(id: string) {
  return useQuery({
    queryKey: ['projects', id],
    queryFn: () => api.get<Project>(`/projects/${id}`),
  })
}

export function useCreateProject() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { title: string; description: string; review_type: ReviewType }) =>
      api.post<Project>('/projects', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['projects'] }),
  })
}

export function useUpdateProject(id: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { title: string; description: string; review_type: ReviewType }) =>
      api.patch<Project>(`/projects/${id}`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['projects'] }),
  })
}

export function useDeleteProject(id: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => api.delete<void>(`/projects/${id}`),
    onSuccess: () => {
      qc.removeQueries({ queryKey: ['projects', id] })
      return qc.invalidateQueries({ queryKey: ['projects'], exact: true })
    },
  })
}

export function useMembers(projectId: string) {
  return useQuery({
    queryKey: ['projects', projectId, 'members'],
    queryFn: () => api.get<Member[]>(`/projects/${projectId}/members`),
  })
}

export function useMemberActions(projectId: string) {
  const qc = useQueryClient()
  const refresh = () => qc.invalidateQueries({ queryKey: ['projects', projectId] })
  return {
    changeRole: useMutation({
      mutationFn: ({ userId, role }: { userId: string; role: Role }) =>
        api.patch<Member>(`/projects/${projectId}/members/${userId}`, { role }),
      onSuccess: refresh,
    }),
    remove: useMutation({
      mutationFn: (userId: string) => api.delete<void>(`/projects/${projectId}/members/${userId}`),
      onSuccess: refresh,
    }),
    invite: useMutation({
      mutationFn: ({ email, role }: { email: string; role: Role }) =>
        api.post<InvitationCreated>('/invitations', { email, role, project_id: projectId }),
    }),
  }
}
