import { memo, useEffect, useState } from 'react';
import { User, Bot, Copy, Check, RotateCcw } from 'lucide-react';
import MarkdownMessage from '../common/MarkdownMessage';
import ExportButton from '../common/ExportButton';

// Affiché entre l'envoi et le premier token : l'utilisateur voit que ça travaille.
export const ThinkingIndicator = ({ label: forced }) => {
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    const t = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, []);

  const label = forced || (seconds < 8 ? 'Thinking' : seconds < 25 ? 'Generating response' : 'Still working');

  return (
    <div className="thinking" role="status" aria-live="polite">
      <span className="thinking-dots" aria-hidden="true"><i /><i /><i /></span>
      <span>{label}…</span>
      {seconds >= 3 && <span className="thinking-time">{seconds}s</span>}
    </div>
  );
};

const MessageItem = ({ message, index, grouped, isStreaming, busy, onRetry, thinkingLabel }) => {
  const [copied, setCopied] = useState(false);
  const isUser = message.role === 'user';

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Copy failed:', err);
    }
  };

  const showActions = !!message.content && !isStreaming;

  return (
    <div
      className={`chat-message ${isUser ? 'chat-message-user' : ''} ${grouped ? 'chat-message-same' : ''}`}
      style={{ marginBottom: grouped ? '0.5rem' : 'var(--spacing-4)', position: 'relative' }}
    >
      <div className="chat-message-avatar">{isUser ? <User size={18} /> : <Bot size={18} />}</div>

      <div className="chat-message-content has-actions">
        {message.content ? (
          <MarkdownMessage content={message.content} isStreaming={isStreaming} />
        ) : (
          <ThinkingIndicator label={thinkingLabel} />
        )}

        {showActions && (
          <div className="message-actions">
            <button type="button" onClick={handleCopy} title="Copy" className={`msg-action ${copied ? 'ok' : ''}`}>
              {copied ? <Check size={12} /> : <Copy size={12} />}
              {copied ? 'Copied' : 'Copy'}
            </button>
            <button
              type="button"
              onClick={() => onRetry(message, index)}
              disabled={busy}
              title={isUser ? 'Retry this message' : 'Regenerate response'}
              className="msg-action"
            >
              <RotateCcw size={12} />
              {isUser ? 'Retry' : 'Regenerate'}
            </button>
            {!isUser && (
              <ExportButton
                content={message.content}
                title={message.content.trim().split(/\s+/).slice(0, 6).join(' ')}
                compact={false}
              />
            )}
          </div>
        )}
      </div>
    </div>
  );
};

// Re-render uniquement si le message, son état de stream ou le groupage change.
export default memo(MessageItem);
