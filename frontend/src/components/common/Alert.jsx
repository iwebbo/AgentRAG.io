import { useEffect, useRef } from 'react';
import { CheckCircle, XCircle, AlertTriangle, Info, X } from 'lucide-react';

const CONFIG = {
  success: { icon: CheckCircle, className: 'alert-success' },
  error: { icon: XCircle, className: 'alert-error' },
  warning: { icon: AlertTriangle, className: 'alert-warning' },
  info: { icon: Info, className: 'alert-info' },
};

// Accepte `message` ou `children`, ainsi que className/style.
const Alert = ({ type = 'info', message, children, onClose, duration = 5000, className = '', style }) => {
  const config = CONFIG[type] || CONFIG.info;
  const Icon = config.icon;

  // Ref : un onClose recréé à chaque rendu ne réinitialise plus le timer.
  const closeRef = useRef(onClose);
  closeRef.current = onClose;

  useEffect(() => {
    if (!duration || !closeRef.current) return undefined;
    const timer = setTimeout(() => closeRef.current && closeRef.current(), duration);
    return () => clearTimeout(timer);
  }, [duration, message]);

  return (
    <div className={`alert ${config.className} ${className}`.trim()} style={style} role="alert">
      <Icon size={18} />
      <div style={{ flex: 1, minWidth: 0 }}>{message ?? children}</div>
      {onClose && (
        <button type="button" className="alert-close" onClick={onClose} aria-label="Close">
          <X size={16} />
        </button>
      )}
    </div>
  );
};

export default Alert;
