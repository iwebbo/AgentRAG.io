import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../../store/authStore';
import {
  LayoutDashboard, MessageSquare, Server, FileText,
  Settings, LogOut, FolderKanban
} from 'lucide-react';

const menuItems = [
  { path: '/',          label: 'Dashboard', icon: LayoutDashboard },
  { path: '/chat',      label: 'Chat',      icon: MessageSquare   },
  { path: '/projects',  label: 'Projects',  icon: FolderKanban    },
  { path: '/agents',    label: 'Agents',    icon: FolderKanban    },
  { path: '/providers', label: 'Providers', icon: Server          },
  { path: '/templates', label: 'Templates', icon: FileText        },
  { path: '/settings',  label: 'Settings',  icon: Settings        },
];

const Sidebar = () => {
  const location = useLocation();
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();

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
          >
            <Icon size={20} />
            <span className="sidebar-item-label">{label}</span>
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