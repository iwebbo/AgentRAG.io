import { create } from 'zustand';
import { authService } from '../services/auth';

export const useAuthStore = create((set) => ({
  user: null,
  loading: false,
  error: null,

  login: async (username, password) => {
    set({ loading: true, error: null });
    try {
      const data = await authService.login(username, password);
      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('refresh_token', data.refresh_token);
      
      const user = await authService.getCurrentUser();
      set({ user, loading: false });
      return true;
    } catch (error) {
      const detail = error.response?.data?.detail;
      const errorMsg = Array.isArray(detail)
        ? detail.map(e => `${e.loc?.slice(-1)[0]}: ${e.msg}`).join(' | ')
        : (typeof detail === 'string' ? detail : 'Login failed');
      set({ error: errorMsg, loading: false });
      return false;
    }
  },

  register: async (username, email, password) => {
    set({ loading: true, error: null });
    try {
      const data = await authService.register(username, email, password);
      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('refresh_token', data.refresh_token);
      
      const user = await authService.getCurrentUser();
      set({ user, loading: false });
      return true;
    } catch (error) {
      const detail = error.response?.data?.detail;
      const errorMsg = Array.isArray(detail)
        ? detail.map(e => `${e.loc?.slice(-1)[0]}: ${e.msg}`).join(' | ')
        : (typeof detail === 'string' ? detail : 'Registration failed');
      set({ error: errorMsg, loading: false });
      return false;
    }
  },

  loadUser: async () => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      set({ user: null, loading: false });
      return;
    }

    set({ loading: true });
    try {
      const user = await authService.getCurrentUser();
      set({ user, loading: false });
    } catch (error) {
      set({ user: null, loading: false });
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
    }
  },

  logout: () => {
    authService.logout();
    set({ user: null, error: null });
  },

  clearError: () => {
    set({ error: null });
  }
}));