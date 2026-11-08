import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import { initTheme } from './theme/theme';
import App from './App.jsx';
import '@fontsource/dm-sans/400.css';
import '@fontsource/dm-sans/500.css';
import '@fontsource/dm-sans/600.css';
import '@fontsource/dm-sans/700.css';
import '@fontsource/dm-mono/400.css';
import '@fontsource/dm-mono/500.css';

// Appliqué avant le premier rendu (index.html le fait aussi, en inline, pour éviter tout flash).
initTheme();

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
