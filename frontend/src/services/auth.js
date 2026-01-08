import api from './api';

export const authService = {
  async register(username, email, password) {
    const response = await api.post('/api/auth/register', {
      username,
      email,
      password
    });
    return response.data;
  },

  async login(username, password) {
    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);

    const response = await api.post('/api/auth/login', formData, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded'
      }
    });
    return response.data;
  },

  async getCurrentUser() {
    const response = await api.get('/api/auth/me');
    return response.data;
  },

  async updateUser(data) {
    const response = await api.put('/api/auth/me', data);
    return response.data;
  },

  logout() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
  }
};