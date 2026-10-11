import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { useMe, useSetupStatus } from './api/hooks'
import { Layout } from './components/Layout'
import AcceptInvite from './pages/AcceptInvite'
import Login from './pages/Login'
import ProjectDetail from './pages/ProjectDetail'
import Projects from './pages/Projects'
import Setup from './pages/Setup'

function Loading() {
  const { t } = useTranslation()
  return <p className="p-8 text-center text-stone-500">{t('app.loading')}</p>
}

function RequireAuth({ children }: { children: ReactNode }) {
  const { data: me, isLoading } = useMe()
  const location = useLocation()
  if (isLoading) return <Loading />
  if (!me) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  return children
}

export default function App() {
  const setup = useSetupStatus()
  const { data: me } = useMe()
  if (setup.isLoading) return <Loading />
  if (setup.data?.needs_setup) return <Setup />

  return (
    <Routes>
      <Route path="/login" element={me ? <Navigate to="/" replace /> : <Login />} />
      <Route path="/convite/:token" element={<AcceptInvite />} />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route index element={<Projects />} />
        <Route path="/projetos/:id" element={<ProjectDetail />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
