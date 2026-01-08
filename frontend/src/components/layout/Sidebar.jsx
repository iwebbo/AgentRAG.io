import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useState, useRef, useEffect } from 'react';
import { useAuthStore } from '../../store/authStore';
import { LayoutDashboard, MessageSquare, Server, FileText, Settings, User, LogOut, ChevronDown, FolderKanban } from 'lucide-react';

const Sidebar = () => {
  const location = useLocation();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const dropdownRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setDropdownOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [dropdownRef]);

  const menuItems = [
    {
      path: '/',
      label: 'Dashboard',
      icon: LayoutDashboard
    },
    {
      path: '/chat',
      label: 'Chat',
      icon: MessageSquare
    },
    {
      path: '/projects',
      label: 'Projects',
      icon: FolderKanban
    },
    {
      path: '/agents',
      label: 'Agents',
      icon: FolderKanban
    },
    {
      path: '/providers',
      label: 'Providers',
      icon: Server
    },
    {
      path: '/templates',
      label: 'Templates',
      icon: FileText
    },
    {
      path: '/settings',
      label: 'Settings',
      icon: Settings
    },
    {
    path: '#', 
    label: 'Logout',
    icon: LogOut,
    onClick: handleLogout 
    }
  ];

  return (
    <aside className="sidebar">
      {/* === LOGO EN HAUT === */}
      <div className="sidebar-top">
        <Link to="/" className="sidebar-logo">
          <img src="/logo.png" alt="RAG.io" className="sidebar-logo-img" />
        </Link>
      </div>

      {/* === MENU PRINCIPAL === */}
      <nav className="sidebar-nav">
        {menuItems.map((item) => {
          const Icon = item.icon;
          const isActive = item.path === '/' 
            ? location.pathname === '/' 
            : location.pathname.startsWith(item.path);

          if (item.label === 'Logout') {
            return (
              <button
                key={item.label}
                className="sidebar-item w-full text-left"
                onClick={item.onClick}
              >
                <Icon size={20} />
                {item.label}
              </button>
            );
          }

          return (
            <Link
              key={item.path}
              to={item.path}
              className={`sidebar-item ${isActive ? 'active' : ''}`}
            >
              <Icon size={20} />
              {item.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
};

export default Sidebar;