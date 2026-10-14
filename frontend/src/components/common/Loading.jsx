import { Loader2 } from 'lucide-react';

const SIZES = { sm: 'loading-spinner-sm', md: '', lg: 'loading-spinner-lg' };

const Loading = ({ message = 'Loading...', size = 'md' }) => (
  <div className="loading-container">
    <Loader2 className={`loading-spinner ${SIZES[size] || ''}`.trim()} />
    {message && <p>{message}</p>}
  </div>
);

export default Loading;
