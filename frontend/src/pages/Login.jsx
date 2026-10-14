import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import Button from '../components/common/Button';
import Alert from '../components/common/Alert';
import { APP_VERSION } from '../version';


const Login = () => {
  const [isRegister, setIsRegister] = useState(false);
  const [formData, setFormData] = useState({ username: '', email: '', password: '' });

  const { login, register, loading, error, clearError, user } = useAuthStore();
  const navigate = useNavigate();

  useEffect(() => {
    if (user) navigate('/');
  }, [user, navigate]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    clearError();

    const success = isRegister
      ? await register(formData.username, formData.email, formData.password)
      : await login(formData.username, formData.password);

    if (success) navigate('/');
  };

  const handleChange = (e) => setFormData({ ...formData, [e.target.name]: e.target.value });

  return (
    <div className="auth-shell">
      <div className="card auth-card">
        <div className="auth-logo">
          <img src="/logo.png" alt="AgentRAG.io" />
        </div>

        <div style={{ textAlign: 'center', marginBottom: 'var(--spacing-6)' }}>
          <h1 style={{ fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--text-heading)', letterSpacing: '-0.01em' }}>
            {isRegister ? 'Create your account' : 'Welcome back'}
          </h1>
          <p style={{ color: 'var(--text-muted)', fontSize: 'var(--text-sm)', marginTop: 4 }}>
            {isRegister ? 'Start building with AgentRAG.io' : 'Sign in to your workspace'}
          </p>
        </div>

        {error && <Alert type="error" message={error} onClose={clearError} duration={5000} />}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label" htmlFor="username">Username</label>
            <input
              id="username"
              type="text"
              name="username"
              className="form-input"
              value={formData.username}
              onChange={handleChange}
              autoComplete="username"
              required
            />
          </div>

          {isRegister && (
            <div className="form-group">
              <label className="form-label" htmlFor="email">Email</label>
              <input
                id="email"
                type="email"
                name="email"
                className="form-input"
                value={formData.email}
                onChange={handleChange}
                autoComplete="email"
                required
              />
            </div>
          )}

          <div className="form-group">
            <label className="form-label" htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              name="password"
              className="form-input"
              value={formData.password}
              onChange={handleChange}
              autoComplete={isRegister ? 'new-password' : 'current-password'}
              required
            />
          </div>

          <Button type="submit" variant="primary" loading={loading} style={{ width: '100%', marginTop: 'var(--spacing-2)' }}>
            {isRegister ? 'Create account' : 'Sign in'}
          </Button>

          <div style={{ textAlign: 'center', marginTop: 'var(--spacing-3)' }}>
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              style={{ border: 'none' }}
              onClick={() => {
                setIsRegister(!isRegister);
                clearError();
              }}
            >
              {isRegister ? 'Already have an account? Sign in' : "Don't have an account? Register"}
            </button>
          </div>
        </form>

        <div style={{ marginTop: 'var(--spacing-6)', paddingTop: 'var(--spacing-4)', borderTop: '1px solid var(--border-subtle)', textAlign: 'center' }}>
          <p style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
            AgentRAG.io version {APP_VERSION}
          </p>
        </div>
      </div>
    </div>
  );
};

export default Login;
