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
      set({ 
        error: error.response?.data?.detail || 'Login failed', 
        loading: false 
      });
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
      set({ 
        error: error.response?.data?.detail || 'Registration failed', 
        loading: false 
      });
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