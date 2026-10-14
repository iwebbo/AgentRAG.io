import { CheckCircle, XCircle, Clock, AlertCircle } from 'lucide-react';

const STATUS = {
  online: { icon: CheckCircle, className: 'badge-success', label: 'Online' },
  offline: { icon: XCircle, className: 'badge-danger', label: 'Offline' },
  pending: { icon: Clock, className: 'badge-warning', label: 'Pending' },
  error: { icon: AlertCircle, className: 'badge-danger', label: 'Error' },
};

const StatusBadge = ({ status }) => {
  const config = STATUS[status] || STATUS.offline;
  const Icon = config.icon;
  return (
    <span className={`badge ${config.className}`}>
      <Icon size={13} />
      {config.label}
    </span>
  );
};

export default StatusBadge;
