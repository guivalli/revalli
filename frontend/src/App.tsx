import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { useMe, useSetupStatus } from './api/hooks'
import { Layout } from './components/Layout'
import AcceptInvite from './pages/AcceptInvite'
import AISettings from './pages/AISettings'
import Login from './pages/Login'
import AI from './pages/project/AI'
import Duplicates from './pages/project/Duplicates'
import Import from './pages/project/Import'
import Members from './pages/project/Members'
import Overview from './pages/project/Overview'
import Protocol from './pages/project/Protocol'
import ProjectLayout from './pages/project/ProjectLayout'
import Records from './pages/project/Records'
import Report from './pages/project/Report'
import Screening from './pages/project/Screening'
import ScreeningSession from './pages/project/ScreeningSession'
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
        <Route path="/ia" element={<AISettings />} />
        <Route path="/projetos/:id" element={<ProjectLayout />}>
          <Route index element={<Overview />} />
          <Route path="referencias" element={<Records />} />
          <Route path="importar" element={<Import />} />
          <Route path="duplicatas" element={<Duplicates />} />
          <Route path="triagem" element={<Screening />} />
          <Route path="triagem/sessao" element={<ScreeningSession />} />
          <Route path="protocolo" element={<Protocol />} />
          <Route path="ia" element={<AI />} />
          <Route path="relatorio" element={<Report />} />
          <Route path="membros" element={<Members />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
