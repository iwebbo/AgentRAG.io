import { CheckCircle, XCircle, Clock, AlertCircle } from 'lucide-react';

const StatusBadge = ({ status }) => {
  const statusConfig = {
    online: {
      icon: CheckCircle,
      className: 'badge-success',
      label: 'Online'
    },
    offline: {
      icon: XCircle,
      className: 'badge-danger',
      label: 'Offline'
    },
    pending: {
      icon: Clock,
      className: 'badge-warning',
      label: 'Pending'
    },
    error: {
      icon: AlertCircle,
      className: 'badge-danger',
      label: 'Error'
    }
  };

  const config = statusConfig[status] || statusConfig.offline;
  const Icon = config.icon;

  return (
    <span className={`badge ${config.className}`}>
      <Icon size={14} />
      {config.label}
    </span>
  );
};

export default StatusBadge;