import { useState, useEffect } from 'react';
import { User, Save } from 'lucide-react';
import Layout from '../components/layout/Layout';
import Button from '../components/common/Button';
import Alert from '../components/common/Alert';
import { useAuthStore } from '../store/authStore';
import api from '../services/api';

const Settings = () => {
  const { user, loadUser } = useAuthStore();
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    confirmPassword: ''
  });
  const [loading, setLoading] = useState(false);
  const [alert, setAlert] = useState(null);

  useEffect(() => {
    if (user) {
      setFormData({
        username: user.username,
        email: user.email,
        password: '',
        confirmPassword: ''
      });
    }
  }, [user]);

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    // Validation
    if (formData.password && formData.password !== formData.confirmPassword) {
      showAlert('error', 'Passwords do not match');
      return;
    }

    if (formData.password && formData.password.length < 8) {
      showAlert('error', 'Password must be at least 8 characters');
      return;
    }

    setLoading(true);

    try {
      const updateData = {
        username: formData.username,
        email: formData.email
      };

      if (formData.password) {
        updateData.password = formData.password;
      }

      await api.put('/api/auth/me', updateData);
      await loadUser();
      
      showAlert('success', 'Profile updated successfully');
      
      // Clear password fields
      setFormData({
        ...formData,
        password: '',
        confirmPassword: ''
      });
    } catch (error) {
      showAlert('error', error.response?.data?.detail || 'Failed to update profile');
    } finally {
      setLoading(false);
    }
  };

  const showAlert = (type, message) => {
    setAlert({ type, message });
    setTimeout(() => setAlert(null), 5000);
  };

  return (
    <Layout>
      <div className="container" style={{ padding: 'var(--spacing-8) var(--spacing-4)' }}>
        {alert && (
          <div style={{ marginBottom: 'var(--spacing-4)' }}>
            <Alert type={alert.type} message={alert.message} onClose={() => setAlert(null)} />
          </div>
        )}

        <div style={{ maxWidth: '800px', margin: '0 auto' }}>
          <div style={{ marginBottom: 'var(--spacing-8)' }}>
            <h1 style={{ fontSize: 'var(--text-3xl)', fontWeight: '700', marginBottom: 'var(--spacing-2)' }}>
              Settings
            </h1>
            <p style={{ color: 'var(--gray-600)' }}>
              Manage your account settings and preferences
            </p>
          </div>

          <div className="card">
            <div className="card-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-3)' }}>
                <User size={24} style={{ color: 'var(--primary)' }} />
                <div>
                  <h2 className="card-title">Profile Information</h2>
                  <p className="card-description">Update your account details</p>
                </div>
              </div>
            </div>

            <form onSubmit={handleSubmit}>
              <div className="form-group">
                <label className="form-label">Username</label>
                <input
                  type="text"
                  name="username"
                  className="form-input"
                  value={formData.username}
                  onChange={handleChange}
                  required
                  minLength={3}
                  maxLength={50}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Email</label>
                <input
                  type="email"
                  name="email"
                  className="form-input"
                  value={formData.email}
                  onChange={handleChange}
                  required
                />
              </div>

              <div style={{ 
                borderTop: '1px solid var(--gray-200)', 
                margin: 'var(--spacing-6) 0',
                paddingTop: 'var(--spacing-6)'
              }}>
                <h3 style={{ 
                  fontSize: 'var(--text-lg)', 
                  fontWeight: '600', 
                  marginBottom: 'var(--spacing-4)' 
                }}>
                  Change Password
                </h3>
                <p style={{ 
                  fontSize: 'var(--text-sm)', 
                  color: 'var(--gray-600)', 
                  marginBottom: 'var(--spacing-4)' 
                }}>
                  Leave blank if you don't want to change your password
                </p>

                <div className="form-group">
                  <label className="form-label">New Password</label>
                  <input
                    type="password"
                    name="password"
                    className="form-input"
                    value={formData.password}
                    onChange={handleChange}
                    minLength={8}
                    placeholder="Enter new password"
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Confirm New Password</label>
                  <input
                    type="password"
                    name="confirmPassword"
                    className="form-input"
                    value={formData.confirmPassword}
                    onChange={handleChange}
                    minLength={8}
                    placeholder="Confirm new password"
                  />
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--spacing-3)' }}>
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => {
                    setFormData({
                      username: user.username,
                      email: user.email,
                      password: '',
                      confirmPassword: ''
                    });
                  }}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  variant="primary"
                  icon={Save}
                  loading={loading}
                >
                  Save Changes
                </Button>
              </div>
            </form>
          </div>

          <div className="card" style={{ marginTop: 'var(--spacing-6)' }}>
            <div className="card-header">
              <h2 className="card-title">Account Information</h2>
              <p className="card-description">View your account details</p>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-3)' }}>
              <div style={{ 
                display: 'flex', 
                justifyContent: 'space-between',
                padding: 'var(--spacing-3)',
                backgroundColor: 'var(--gray-50)',
                borderRadius: 'var(--radius)'
              }}>
                <span style={{ fontWeight: '500', color: 'var(--gray-700)' }}>Account Status</span>
                <span style={{ color: 'var(--success)' }}>Active</span>
              </div>

              <div style={{ 
                display: 'flex', 
                justifyContent: 'space-between',
                padding: 'var(--spacing-3)',
                backgroundColor: 'var(--gray-50)',
                borderRadius: 'var(--radius)'
              }}>
                <span style={{ fontWeight: '500', color: 'var(--gray-700)' }}>Member Since</span>
                <span style={{ color: 'var(--gray-600)' }}>
                  {user && new Date(user.created_at).toLocaleDateString()}
                </span>
              </div>

              <div style={{ 
                display: 'flex', 
                justifyContent: 'space-between',
                padding: 'var(--spacing-3)',
                backgroundColor: 'var(--gray-50)',
                borderRadius: 'var(--radius)'
              }}>
                <span style={{ fontWeight: '500', color: 'var(--gray-700)' }}>Last Updated</span>
                <span style={{ color: 'var(--gray-600)' }}>
                  {user && new Date(user.updated_at).toLocaleDateString()}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
};

export default Settings;