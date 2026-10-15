import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/AppShell'
import { DashboardPage } from './pages/DashboardPage'
import { DocsPage } from './pages/DocsPage'
import { InvestigationPage } from './pages/InvestigationPage'
import { LandingPage } from './pages/LandingPage'
import { NewInvestigationPage } from './pages/NewInvestigationPage'
import { SettingsPage } from './pages/SettingsPage'

export default function App() {
  return <BrowserRouter><Routes><Route path="/" element={<LandingPage />} /><Route path="/docs" element={<DocsPage />} /><Route element={<AppShell />}><Route path="/app" element={<DashboardPage />} /><Route path="/app/new" element={<NewInvestigationPage />} /><Route path="/app/investigations/:id" element={<InvestigationPage />} /><Route path="/app/settings" element={<SettingsPage />} /></Route><Route path="*" element={<LandingPage />} /></Routes></BrowserRouter>
}
