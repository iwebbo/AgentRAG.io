import { Loader2 } from 'lucide-react';

const Loading = ({ message = 'Loading...', size = 'md' }) => {
  const sizeClasses = {
    sm: 'loading-spinner-sm',
    md: '',
    lg: 'loading-spinner-lg'
  };

  return (
    <div className="loading-container">
      <Loader2 className={`loading-spinner ${sizeClasses[size]}`} />
      {message && <p style={{ color: 'var(--gray-600)' }}>{message}</p>}
    </div>
  );
};

export default Loading;