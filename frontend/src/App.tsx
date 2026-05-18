import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Navbar from './components/shared/Navbar'
import AuthGuard from './components/shared/AuthGuard'
import CalendarPage from './pages/CalendarPage'
import NewPostPage from './pages/NewPostPage'
import EditPostPage from './pages/EditPostPage'
import DraftsPage from './pages/DraftsPage'
import SettingsPage from './pages/SettingsPage'
import StatsPage from './pages/StatsPage'
import LoginPage from './pages/LoginPage'

function ProtectedShell({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <Navbar />
      {children}
    </AuthGuard>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<ProtectedShell><CalendarPage /></ProtectedShell>} />
        <Route path="/posts/new" element={<ProtectedShell><NewPostPage /></ProtectedShell>} />
        <Route path="/posts/:id/edit" element={<ProtectedShell><EditPostPage /></ProtectedShell>} />
        <Route path="/drafts" element={<ProtectedShell><DraftsPage /></ProtectedShell>} />
        <Route path="/stats" element={<ProtectedShell><StatsPage /></ProtectedShell>} />
        <Route path="/settings" element={<ProtectedShell><SettingsPage /></ProtectedShell>} />
      </Routes>
    </BrowserRouter>
  )
}
