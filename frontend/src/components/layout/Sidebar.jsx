import { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard, MessageSquare, Server, FileText,
  Settings, LogOut, FolderKanban, CalendarClock, Bot, Moon, Sun,
} from 'lucide-react';
import { useAuthStore } from '../../store/authStore';
import api from '../../services/api';
import { useTheme } from '../../theme/theme';

const menuItems = [
  { path: '/',          label: 'Dashboard', icon: LayoutDashboard },
  { path: '/chat',      label: 'Chat',      icon: MessageSquare   },
  { path: '/projects',  label: 'Projects',  icon: FolderKanban    },
  { path: '/agents',    label: 'Agents',    icon: Bot             },
  { path: '/scheduler', label: 'Scheduler', icon: CalendarClock   },
  { path: '/providers', label: 'Providers', icon: Server          },
  { path: '/templates', label: 'Templates', icon: FileText        },
  { path: '/settings',  label: 'Settings',  icon: Settings        },
];

const Sidebar = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { logout } = useAuthStore();
  const { theme, toggleTheme } = useTheme();
  const [unread, setUnread] = useState(0);

  // Badge notifications non lues (polling, best-effort)
  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const res = await api.get('/api/notifications/unread-count');
        if (!cancelled) setUnread(res.data.count || 0);
      } catch (_) {
        /* best-effort */
      }
    };
    load();
    const timer = setInterval(() => {
      if (document.visibilityState === 'visible') load();
    }, 30000);
    window.addEventListener('notifications-changed', load);
    return () => {
      cancelled = true;
      clearInterval(timer);
      window.removeEventListener('notifications-changed', load);
    };
  }, [location.pathname]);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const isActive = (path) =>
    path === '/' ? location.pathname === '/' : location.pathname.startsWith(path);

  return (
    <aside className="sidebar">
      <div className="sidebar-top">
        <Link to="/" className="sidebar-logo">
          <img src="/logo.png" alt="AgentRAG.io" className="sidebar-logo-img" />
          <span className="sidebar-logo-text">
            <span className="sidebar-logo-label">AgentRAG.io</span>
            <span className="sidebar-logo-sub">workspace</span>
          </span>
        </Link>
      </div>

      <nav className="sidebar-nav">
        {menuItems.map(({ path, label, icon: Icon }) => (
          <Link
            key={path}
            to={path}
            className={`sidebar-item ${isActive(path) ? 'active' : ''}`}
            title={label}
          >
            <Icon size={18} />
            <span className="sidebar-item-label">{label}</span>
            {path === '/scheduler' && unread > 0 && (
              <span className="sidebar-badge">{unread > 99 ? '99+' : unread}</span>
            )}
          </Link>
        ))}
      </nav>

      <div className="sidebar-footer">
        <button type="button" className="sidebar-item" onClick={toggleTheme} title="Toggle theme">
          {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
          <span className="sidebar-item-label">{theme === 'dark' ? 'Light theme' : 'Dark theme'}</span>
        </button>
        <button type="button" className="sidebar-item danger" onClick={handleLogout} title="Logout">
          <LogOut size={18} />
          <span className="sidebar-item-label">Logout</span>
        </button>
      </div>
    </aside>
  );
};

export default Sidebar;
