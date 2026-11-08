// Gestion du thème (dark par défaut), persistance dans localStorage('app-theme').
// Thèmes : dark | light | glass (clair) | glass-dark.
// Même clé que le template : réutilisable à l'identique dans les futures apps.
import { useCallback, useEffect, useState } from 'react';

const KEY = 'app-theme';
const EVENT = 'app-theme-change';
const DEFAULT_THEME = 'dark';

export const THEMES = ['dark', 'light', 'glass', 'glass-dark'];

export const THEME_LABELS = {
  dark: 'Dark',
  light: 'Light',
  glass: 'Glass',
  'glass-dark': 'Glass Dark',
};

// Couleur de la barre du navigateur mobile (<meta name="theme-color">)
const THEME_COLORS = {
  dark: '#09090b',
  light: '#f8fafc',
  glass: '#F3F5FB',
  'glass-dark': '#151B2F',
};

const isTheme = (v) => THEMES.includes(v);

const safeGet = () => {
  try {
    const v = localStorage.getItem(KEY);
    return isTheme(v) ? v : DEFAULT_THEME;
  } catch (_) {
    return DEFAULT_THEME;
  }
};

const syncMetaColor = (theme) => {
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute('content', THEME_COLORS[theme]);
};

export const applyTheme = (theme) => {
  const next = isTheme(theme) ? theme : DEFAULT_THEME;
  document.documentElement.setAttribute('data-theme', next);
  syncMetaColor(next);
  try {
    localStorage.setItem(KEY, next);
  } catch (_) {
    /* stockage indisponible : le thème reste appliqué pour la session */
  }
  window.dispatchEvent(new CustomEvent(EVENT, { detail: next }));
  return next;
};

export const initTheme = () => {
  const theme = safeGet();
  document.documentElement.setAttribute('data-theme', theme);
  syncMetaColor(theme);
};

export const useTheme = () => {
  const [theme, setThemeState] = useState(() => {
    const attr = document.documentElement.getAttribute('data-theme');
    return isTheme(attr) ? attr : safeGet();
  });

  useEffect(() => {
    const onChange = (e) => setThemeState(e.detail);
    window.addEventListener(EVENT, onChange);
    return () => window.removeEventListener(EVENT, onChange);
  }, []);

  const setTheme = useCallback((t) => setThemeState(applyTheme(t)), []);

  // Cycle sur tous les thèmes : dark → light → glass → glass-dark → dark
  const toggleTheme = useCallback(() => {
    const next = THEMES[(THEMES.indexOf(theme) + 1) % THEMES.length];
    setThemeState(applyTheme(next));
  }, [theme]);

  return { theme, themes: THEMES, setTheme, toggleTheme };
};