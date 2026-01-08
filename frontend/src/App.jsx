import { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useAuthStore } from './store/authStore';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Chat from './pages/Chat';
import Providers from './pages/Providers';
import Settings from './pages/Settings';
import Templates from './pages/Templates';
import Projects from './pages/Projects';
import Agents from './pages/Agents';
import RAGChat from './pages/RAGChat'; 
import Documents from './pages/Documents';
import Loading from './components/common/Loading';
import './assets/styles/main.css';

const PrivateRoute = ({ children }) => {
  const { user } = useAuthStore();
  return user ? children : <Navigate to="/login" />;
};

function App() {
  const { user, loading, loadUser } = useAuthStore();

  useEffect(() => {
    loadUser();
  }, []);

  if (loading) {
    return <Loading message="Loading application..." />;
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/"
          element={
            <PrivateRoute>
              <Dashboard />
            </PrivateRoute>
          }
        />
        <Route
          path="/chat/:id?"
          element={
            <PrivateRoute>
              <Chat />
            </PrivateRoute>
          }
        />
        <Route
          path="/projects"
          element={
            <PrivateRoute>
              <Projects />
            </PrivateRoute>
          }
        />
        <Route
          path="/projects/:projectId/chat"  // ← AJOUTER
          element={
            <PrivateRoute>
              <RAGChat />
            </PrivateRoute>
          }
        />
        <Route
          path="/projects/:projectId/documents"
          element={
            <PrivateRoute>
              <Documents />
            </PrivateRoute>
          }
        />
        <Route
          path="/documents"
          element={
            <PrivateRoute>
              <Documents />
            </PrivateRoute>
          }
        />
        <Route
          path="/agents"
          element={
            <PrivateRoute>
              <Agents />
            </PrivateRoute>
          }
        />
        <Route
          path="/providers"
          element={
            <PrivateRoute>
              <Providers />
            </PrivateRoute>
          }
        />
        <Route
          path="/templates"
          element={
            <PrivateRoute>
              <Templates />
            </PrivateRoute>
          }
        />
        <Route
          path="/settings"
          element={
            <PrivateRoute>
              <Settings />
            </PrivateRoute>
          }
        />
      </Routes>
    </BrowserRouter>
  );
}

export default App;