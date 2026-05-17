import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Navbar from './components/shared/Navbar'
import CalendarPage from './pages/CalendarPage'
import NewPostPage from './pages/NewPostPage'
import EditPostPage from './pages/EditPostPage'
import DraftsPage from './pages/DraftsPage'
import SettingsPage from './pages/SettingsPage'
import StatsPage from './pages/StatsPage'

export default function App() {
  return (
    <BrowserRouter>
      <Navbar />
      <Routes>
        <Route path="/" element={<CalendarPage />} />
        <Route path="/posts/new" element={<NewPostPage />} />
        <Route path="/posts/:id/edit" element={<EditPostPage />} />
        <Route path="/drafts" element={<DraftsPage />} />
        <Route path="/stats" element={<StatsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Routes>
    </BrowserRouter>
  )
}
