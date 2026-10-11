import { lazy, Suspense, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { useMe, useSetupStatus } from './api/hooks'
import { Layout } from './components/Layout'
import AcceptInvite from './pages/AcceptInvite'
import Login from './pages/Login'
import Duplicates from './pages/project/Duplicates'
import Import from './pages/project/Import'
import Members from './pages/project/Members'
import Overview from './pages/project/Overview'
import Protocol from './pages/project/Protocol'
import ProjectLayout from './pages/project/ProjectLayout'
import Records from './pages/project/Records'
import Screening from './pages/project/Screening'
import ScreeningSession from './pages/project/ScreeningSession'
import Projects from './pages/Projects'
import Setup from './pages/Setup'

// Telas menos usadas ficam em pacotes separados, baixados na primeira visita
const Extraction = lazy(() => import('./pages/project/Extraction'))
const ExtractionUnit = lazy(() => import('./pages/project/ExtractionUnit'))
const FormBuilder = lazy(() => import('./pages/project/FormBuilder'))
const Report = lazy(() => import('./pages/project/Report'))
const Coding = lazy(() => import('./pages/project/Coding'))
const CodingUnit = lazy(() => import('./pages/project/CodingUnit'))
const Meta = lazy(() => import('./pages/project/Meta'))
const Grade = lazy(() => import('./pages/project/Grade'))
const AI = lazy(() => import('./pages/project/AI'))
const AISettings = lazy(() => import('./pages/AISettings'))

function Lazy({ children }: { children: ReactNode }) {
  const { t } = useTranslation()
  return <Suspense fallback={<p className="text-stone-500">{t('app.loading')}</p>}>{children}</Suspense>
}


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
        <Route path="/ia" element={<Lazy><AISettings /></Lazy>} />
        <Route path="/projetos/:id" element={<ProjectLayout />}>
          <Route index element={<Overview />} />
          <Route path="referencias" element={<Records />} />
          <Route path="importar" element={<Import />} />
          <Route path="duplicatas" element={<Duplicates />} />
          <Route path="triagem" element={<Screening />} />
          <Route path="triagem/sessao" element={<ScreeningSession />} />
          <Route path="protocolo" element={<Protocol />} />
          <Route path="ia" element={<Lazy><AI /></Lazy>} />
          <Route path="extracao" element={<Lazy><Extraction /></Lazy>} />
          <Route path="extracao/novo" element={<Lazy><FormBuilder /></Lazy>} />
          <Route path="extracao/:formId/editar" element={<Lazy><FormBuilder /></Lazy>} />
          <Route path="extracao/:formId/:recordId" element={<Lazy><ExtractionUnit /></Lazy>} />
          <Route path="sintese" element={<Lazy><Coding /></Lazy>} />
          <Route path="sintese/meta" element={<Lazy><Meta /></Lazy>} />
          <Route path="sintese/grade" element={<Lazy><Grade /></Lazy>} />
          <Route path="sintese/:recordId" element={<Lazy><CodingUnit /></Lazy>} />
          <Route path="relatorio" element={<Lazy><Report /></Lazy>} />
          <Route path="membros" element={<Members />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
