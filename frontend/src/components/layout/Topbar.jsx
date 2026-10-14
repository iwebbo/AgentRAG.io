import { useLocation } from 'react-router-dom';
import { Moon, Sun } from 'lucide-react';
import { useTheme } from '../../theme/theme';
import { APP_VERSION } from '../../version';


const SECTIONS = {
  '': 'Dashboard',
  chat: 'Chat',
  projects: 'Projects',
  documents: 'Documents',
  agents: 'Agents',
  scheduler: 'Scheduler',
  providers: 'Providers',
  templates: 'Templates',
  settings: 'Settings',
};

const SUB = { chat: 'RAG Chat', documents: 'Documents' };

const Topbar = () => {
  const { pathname } = useLocation();
  const { theme, toggleTheme } = useTheme();

  const parts = pathname.split('/').filter(Boolean);
  const root = parts[0] || '';
  let current = SECTIONS[root] || root;
  // /projects/:id/chat | /projects/:id/documents
  if (root === 'projects' && parts[2]) current = `Projects / ${SUB[parts[2]] || parts[2]}`;

  return (
    <header className="topbar">
      <div className="topbar-crumbs">
        <span className="muted">AgentRAG.io</span>
        <span className="sep">/</span>
        <span className="current">{current}</span>
      </div>
      <div className="topbar-right">
        <span className="topbar-chip">v{APP_VERSION}</span>
        <button
          type="button"
          className="topbar-btn"
          onClick={toggleTheme}
          title={theme === 'dark' ? 'Light theme' : 'Dark theme'}
          aria-label="Toggle theme"
        >
          {theme === 'dark' ? <Sun size={14} /> : <Moon size={14} />}
        </button>
      </div>
    </header>
  );
};

export default Topbar;
