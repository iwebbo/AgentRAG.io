import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import Button from '../components/common/Button';
import Alert from '../components/common/Alert';

import logo from '../../public/logo.png';

const Login = () => {
  const [isRegister, setIsRegister] = useState(false);
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: ''
  });

  const { login, register, loading, error, clearError, user } = useAuthStore();
  const navigate = useNavigate();

  useEffect(() => {
    if (user) {
      navigate('/');
    }
  }, [user, navigate]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    clearError();

    if (isRegister) {
      const success = await register(formData.username, formData.email, formData.password);
      if (success) {
        navigate('/');
      }
    } else {
      const success = await login(formData.username, formData.password);
      if (success) {
        navigate('/');
      }
    }
  };

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  return (
    <div style={{ 
      display: 'flex', 
      alignItems: 'center', 
      justifyContent: 'center', 
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #0ea5e9 0%, #6366f1 50%, #a855f7 100%)',
      padding: 'var(--spacing-4)'
    }}>
      <div className="card" style={{ width: '100%', maxWidth: '400px' }}>
        <div className="card-header" style={{ textAlign: 'center' }}>
          {/* LOGO TRANSPARENT */}
          <div style={{ 
            marginBottom: 'var(--spacing-4)',
            width: '300px',
            height: '300px',
            margin: '0 auto',
            display: 'flex',
            alignItems: 'center',
            display: 'flex', 
            justifyContent: 'center' 
          }}>
            <img 
              src={logo} 
              alt="LLM.io Logo" 
              style={{
                width: '100%',
                height: '100%',
                objectFit: 'contain'
              }}
            />
          </div>

          <h1 style={{
              fontSize: '1.875rem',
              fontWeight: 700,
              color: 'var(--text-primary)',
              marginTop: '1rem',
              marginBottom: '0.5rem'
            }}>
            Welcome Back
          </h1>
          <p style={{ color: 'rgba(24, 24, 24, 0.97)', fontSize: '0.95rem' }}>
            {isRegister ? 'Create your account' : 'Sign in to your account'}
          </p>
        </div>

        {error && (
          <Alert 
            type="error" 
            message={error} 
            onClose={clearError}
            duration={5000}
          />
        )}

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
            />
          </div>

          {isRegister && (
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
          )}

          <div className="form-group">
            <label className="form-label">Password</label>
            <input
              type="password"
              name="password"
              className="form-input"
              value={formData.password}
              onChange={handleChange}
              required
            />
          </div>

          <Button
            type="submit"
            variant="primary"
            loading={loading}
            style={{ width: '100%', marginBottom: 'var(--spacing-4)' }}
          >
            {isRegister ? 'Create Account' : 'Sign In'}
          </Button>

          <div style={{ textAlign: 'center' }}>
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => {
                setIsRegister(!isRegister);
                clearError();
              }}
              style={{ color: 'rgba(68, 68, 68, 0.93)', fontSize: '0.9rem' }}
            >
              {isRegister ? 'Already have an account? Sign in' : "Don't have an account? Register"}
            </button>
          </div>
        </form>

       {/* Footer */}
        <div
          style={{
            marginTop: '2rem',
            paddingTop: '1.5rem',
            borderTop: '1px solid var(--border-light)',
            textAlign: 'center'
          }}
        >
          <p style={{ fontSize: '0.813rem', color: 'var(--text-tertiary)' }}>
            AgentRAG.io version 1.0
          </p>
        </div>
      </div>
    </div>
  );
};

export default Login;