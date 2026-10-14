/**
 * ExportButton — dropdown d'export d'un message LLM (html / xlsx / docx / pdf)
 * Props : content {string}, title {string}, compact {boolean}
 */
import { useState, useRef, useEffect } from 'react';
import { Download, FileText, FileSpreadsheet, Globe, File, Loader2, ChevronDown, Check } from 'lucide-react';
import { useExport } from '../../hooks/useExport';

const FORMATS = [
  { id: 'html', label: 'HTML', description: 'Page web standalone', icon: Globe, tone: 'warning' },
  { id: 'xlsx', label: 'Excel', description: 'Tableur (.xlsx)', icon: FileSpreadsheet, tone: 'success' },
  { id: 'docx', label: 'Word', description: 'Document Word (.docx)', icon: FileText, tone: 'info' },
  { id: 'pdf', label: 'PDF', description: 'Document PDF', icon: File, tone: 'danger' },
];

export default function ExportButton({ content, title, compact = false }) {
  const [open, setOpen] = useState(false);
  const [activeFormat, setActiveFormat] = useState(null);
  const [success, setSuccess] = useState(null);
  const rootRef = useRef(null);
  const { exportContent, exporting, exportError } = useExport();

  useEffect(() => {
    if (!open) return undefined;
    const handler = (e) => {
      if (rootRef.current && !rootRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  const handleExport = async (format) => {
    setActiveFormat(format);
    try {
      const suggestedTitle = title || content.trim().split(/\s+/).slice(0, 6).join(' ');
      await exportContent(content, format, suggestedTitle);
      setSuccess(format);
      setTimeout(() => { setSuccess(null); setOpen(false); }, 1200);
    } catch {
      /* exportError est déjà positionné par le hook */
    } finally {
      setActiveFormat(null);
    }
  };

  const isLoading = exporting && activeFormat !== null;

  return (
    <div ref={rootRef} style={{ position: 'relative', display: 'inline-block' }}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        disabled={isLoading}
        title="Exporter ce message"
        style={{
          display: 'flex', alignItems: 'center', gap: 4,
          padding: compact ? '3px 6px' : '3px 8px',
          fontSize: 'var(--text-xs)', fontFamily: 'inherit',
          color: open ? 'var(--accent-fg)' : 'var(--text-secondary)',
          background: open ? 'var(--accent-bg)' : 'var(--bg-surface-hover)',
          border: `1px solid ${open ? 'var(--accent-bd)' : 'var(--border-subtle)'}`,
          borderRadius: 'var(--radius-sm)',
          cursor: isLoading ? 'wait' : 'pointer',
          transition: 'all 0.15s ease',
          opacity: isLoading ? 0.7 : 1,
          fontWeight: open ? 600 : 400,
        }}
      >
        {isLoading ? <Loader2 size={12} className="animate-spin" /> : <Download size={12} />}
        {!compact && (
          <>
            {isLoading ? 'Export...' : 'Exporter'}
            <ChevronDown size={10} style={{ transform: open ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }} />
          </>
        )}
      </button>

      {open && (
        <div
          style={{
            position: 'absolute', bottom: 'calc(100% + 6px)', left: 0, zIndex: 200,
            background: 'var(--bg-surface)', border: '1px solid var(--border-hover)',
            borderRadius: 'var(--radius-card)', boxShadow: 'var(--shadow-panel)',
            minWidth: 230, overflow: 'hidden', animation: 'fadeIn 0.18s ease',
          }}
        >
          <div className="section-label" style={{ padding: '10px 14px 6px', borderBottom: '1px solid var(--border-subtle)' }}>
            Choisir le format
          </div>

          {FORMATS.map((fmt) => {
            const Icon = fmt.icon;
            const isThis = activeFormat === fmt.id;
            const isDone = success === fmt.id;
            return (
              <button
                key={fmt.id}
                type="button"
                onClick={() => !isLoading && handleExport(fmt.id)}
                disabled={isLoading}
                className="menu-item"
                style={isDone ? { background: `var(--${fmt.tone}-bg)` } : undefined}
              >
                <span
                  style={{
                    width: 30, height: 30, borderRadius: 'var(--radius-md)', flexShrink: 0,
                    background: `var(--${fmt.tone}-bg)`, border: `1px solid var(--${fmt.tone}-bd)`,
                    color: `var(--${fmt.tone}-fg)`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                  }}
                >
                  {isThis ? <Loader2 size={14} className="animate-spin" /> : isDone ? <Check size={14} /> : <Icon size={14} />}
                </span>
                <span style={{ display: 'block', minWidth: 0 }}>
                  <span style={{ display: 'block', fontSize: 13, fontWeight: 600, color: 'var(--text-heading)', lineHeight: 1.2 }}>
                    {fmt.label}
                    {isDone && <span style={{ color: 'var(--success-fg)', marginLeft: 6, fontWeight: 400 }}>Téléchargé !</span>}
                  </span>
                  <span style={{ display: 'block', fontSize: 11, color: 'var(--text-muted)', marginTop: 1 }}>{fmt.description}</span>
                </span>
              </button>
            );
          })}

          {exportError && (
            <div
              style={{
                padding: '8px 14px', fontSize: 11, color: 'var(--danger-fg)',
                background: 'var(--danger-bg)', borderTop: '1px solid var(--danger-bd)',
              }}
            >
              ⚠ {exportError}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
