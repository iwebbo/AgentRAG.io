import api from './api';

const unwrap = (promise) => promise.then((res) => res.data);

export const schedulerApi = {
  catalog: () => unwrap(api.get('/api/scheduler/catalog')),

  validate: (payload, taskId) =>
    unwrap(api.post('/api/scheduler/tasks/validate', payload, { params: taskId ? { task_id: taskId } : {} })),

  listTasks: () => unwrap(api.get('/api/scheduler/tasks')),
  createTask: (payload) => unwrap(api.post('/api/scheduler/tasks', payload)),
  updateTask: (id, payload) => unwrap(api.put(`/api/scheduler/tasks/${id}`, payload)),
  deleteTask: (id) => api.delete(`/api/scheduler/tasks/${id}`),
  toggleTask: (id) => unwrap(api.patch(`/api/scheduler/tasks/${id}/toggle`)),
  runTask: (id, confirm = false) => unwrap(api.post(`/api/scheduler/tasks/${id}/run`, { confirm })),

  listRuns: (params = {}) => unwrap(api.get('/api/scheduler/runs', { params })),
  getRun: (id) => unwrap(api.get(`/api/scheduler/runs/${id}`)),
  approveRun: (id) => unwrap(api.post(`/api/scheduler/runs/${id}/approve`)),
  rejectRun: (id) => unwrap(api.post(`/api/scheduler/runs/${id}/reject`)),

  listNotifications: (params = {}) => unwrap(api.get('/api/notifications', { params })),
  unreadCount: () => unwrap(api.get('/api/notifications/unread-count')),
  markRead: (id) => unwrap(api.post(`/api/notifications/${id}/read`)),
  markAllRead: () => unwrap(api.post('/api/notifications/read-all')),
  deleteNotification: (id) => api.delete(`/api/notifications/${id}`),
};

// Turns an axios error into a readable message
export const errorMessage = (e) => {
  const detail = e?.response?.data?.detail;
  if (!detail) return e?.message || 'Unexpected error';
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map((d) => d.msg || JSON.stringify(d)).join('; ');
  if (detail.errors) return detail.errors.join('; ');
  return detail.reason || detail.message || JSON.stringify(detail);
};
