import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import { initTheme } from './theme/theme';
import App from './App.jsx';

// Appliqué avant le premier rendu (index.html le fait aussi, en inline, pour éviter tout flash).
initTheme();

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
