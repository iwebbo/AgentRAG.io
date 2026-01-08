//import Header from './Header';
import Sidebar from './Sidebar';

const Layout = ({ children, showSidebar = true }) => {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      <div style={{ display: 'flex', flex: 1 }}>
        {showSidebar && <Sidebar />}
        <main style={{ flex: 1, overflow: 'auto' }}>
          {children}
        </main>
      </div>
    </div>
  );
};

export default Layout;