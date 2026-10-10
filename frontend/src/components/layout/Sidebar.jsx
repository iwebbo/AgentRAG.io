import { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../../store/authStore';
import api from '../../services/api';
import {
  LayoutDashboard, MessageSquare, Server, FileText,
  Settings, LogOut, FolderKanban, CalendarClock
} from 'lucide-react';

const menuItems = [
  { path: '/',          label: 'Dashboard', icon: LayoutDashboard },
  { path: '/chat',      label: 'Chat',      icon: MessageSquare   },
  { path: '/projects',  label: 'Projects',  icon: FolderKanban    },
  { path: '/agents',    label: 'Agents',    icon: FolderKanban    },
  { path: '/scheduler', label: 'Scheduler', icon: CalendarClock   },
  { path: '/providers', label: 'Providers', icon: Server          },
  { path: '/templates', label: 'Templates', icon: FileText        },
  { path: '/settings',  label: 'Settings',  icon: Settings        },
];

const Sidebar = () => {
  const location = useLocation();
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();
  const [unread, setUnread] = useState(0);

  // Unread notifications badge (polling, no websocket)
  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const res = await api.get('/api/notifications/unread-count');
        if (!cancelled) setUnread(res.data.count || 0);
      } catch (_) {
        /* badge is best-effort */
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

      {/* Logo */}
      <div className="sidebar-top">
        <Link to="/" className="sidebar-logo">
          <img src="/logo.png" alt="RAG.io" className="sidebar-logo-img" />
          <span className="sidebar-logo-label">AgentRAG.io</span>
        </Link>
      </div>

      {/* Nav principale */}
      <nav className="sidebar-nav">
        {menuItems.map(({ path, label, icon: Icon }) => (
          <Link
            key={path}
            to={path}
            className={`sidebar-item ${isActive(path) ? 'active' : ''}`}
            title={label}
            style={{ position: 'relative' }}
          >
            <Icon size={20} />
            <span className="sidebar-item-label">{label}</span>
            {path === '/scheduler' && unread > 0 && (
              <span
                style={{
                  position: 'absolute', top: '4px', left: '24px', minWidth: '16px', height: '16px',
                  padding: '0 4px', borderRadius: '99px', background: 'var(--danger-dark)', color: '#fff',
                  fontSize: '10px', fontWeight: 700, lineHeight: '16px', textAlign: 'center',
                }}
              >
                {unread > 99 ? '99+' : unread}
              </span>
            )}
          </Link>
        ))}
      </nav>

      {/* Footer — Logout */}
      <div className="sidebar-footer">
        <button
          className="sidebar-item w-full text-left"
          onClick={handleLogout}
          title="Logout"
        >
          <LogOut size={20} />
          <span className="sidebar-item-label">Logout</span>
        </button>
      </div>

    </aside>
  );
};

export default Sidebar;