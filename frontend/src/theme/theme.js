// Gestion du thème (dark par défaut), persistance dans localStorage('app-theme').
// Même clé que le template : réutilisable à l'identique dans les futures apps.
import { useCallback, useEffect, useState } from 'react';

const KEY = 'app-theme';
const THEMES = ['dark', 'light'];
const EVENT = 'app-theme-change';

const safeGet = () => {
  try {
    const v = localStorage.getItem(KEY);
    return THEMES.includes(v) ? v : 'dark';
  } catch (_) {
    return 'dark';
  }
};

export const applyTheme = (theme) => {
  const next = THEMES.includes(theme) ? theme : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  try {
    localStorage.setItem(KEY, next);
  } catch (_) {
    /* stockage indisponible : le thème reste appliqué pour la session */
  }
  window.dispatchEvent(new CustomEvent(EVENT, { detail: next }));
  return next;
};

export const initTheme = () => {
  document.documentElement.setAttribute('data-theme', safeGet());
};

export const useTheme = () => {
  const [theme, setThemeState] = useState(() => document.documentElement.getAttribute('data-theme') || safeGet());

  useEffect(() => {
    const onChange = (e) => setThemeState(e.detail);
    window.addEventListener(EVENT, onChange);
    return () => window.removeEventListener(EVENT, onChange);
  }, []);

  const setTheme = useCallback((t) => setThemeState(applyTheme(t)), []);
  const toggleTheme = useCallback(() => setThemeState(applyTheme(theme === 'dark' ? 'light' : 'dark')), [theme]);

  return { theme, setTheme, toggleTheme };
};
