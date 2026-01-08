import { useEffect } from 'react';
import { CheckCircle, XCircle, AlertTriangle, Info, X } from 'lucide-react';

const Alert = ({ type = 'info', message, onClose, duration = 5000 }) => {
  const alertConfig = {
    success: {
      icon: CheckCircle,
      className: 'alert-success'
    },
    error: {
      icon: XCircle,
      className: 'alert-error'
    },
    warning: {
      icon: AlertTriangle,
      className: 'alert-warning'
    },
    info: {
      icon: Info,
      className: 'alert-info'
    }
  };

  const config = alertConfig[type] || alertConfig.info;
  const Icon = config.icon;

  useEffect(() => {
    if (duration && onClose) {
      const timer = setTimeout(() => {
        onClose();
      }, duration);

      return () => clearTimeout(timer);
    }
  }, [duration, onClose]);

  return (
    <div className={`alert ${config.className}`}>
      <Icon size={20} />
      <div style={{ flex: 1 }}>{message}</div>
      {onClose && (
        <button className="alert-close" onClick={onClose} style={{ background: 'none', border: 'none' }}>
          <X size={18} />
        </button>
      )}
    </div>
  );
};

export default Alert;