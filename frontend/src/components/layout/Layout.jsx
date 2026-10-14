import Sidebar from './Sidebar';
import Topbar from './Topbar';

const Layout = ({ children, showSidebar = true }) => (
  <div className="app-layout">
    {showSidebar && (
      <div className="sidebar-rail">
        <Sidebar />
      </div>
    )}
    <div className="main-content">
      <Topbar />
      <main className="main-scroll">{children}</main>
    </div>
  </div>
);

export default Layout;
