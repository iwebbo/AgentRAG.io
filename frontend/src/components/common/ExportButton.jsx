/**
 * ExportButton — dropdown d'export d'un message LLM
 *   · « Détecté dans ce message » : fichiers livrables extraits des blocs de code
 *     (Jenkinsfile, .groovy, Dockerfile, values.yaml, README.md…) + ZIP — 100 % local
 *   · Formats document : md (local) / html / xlsx / docx / pdf (backend)
 * Props : content {string}, title {string}, compact {boolean}
 */
import { useState, useRef, useEffect, useMemo } from 'react';
import {
  Download, FileText, FileSpreadsheet, Globe, File, Loader2, ChevronDown, Check,
  FileCode, FileArchive, Hash,
} from 'lucide-react';
import { useExport } from '../../hooks/useExport';
import { extractFiles, exportableFiles } from '../../utils/codeBlocks';

const FORMATS = [
  { id: 'md', label: 'Markdown', description: 'Message complet (.md)', icon: Hash, tone: 'accent' },
  { id: 'html', label: 'HTML', description: 'Page web standalone', icon: Globe, tone: 'warning' },
  { id: 'xlsx', label: 'Excel', description: 'Tableur (.xlsx)', icon: FileSpreadsheet, tone: 'success' },
  { id: 'docx', label: 'Word', description: 'Document Word (.docx)', icon: FileText, tone: 'info' },
  { id: 'pdf', label: 'PDF', description: 'Document PDF', icon: File, tone: 'danger' },
];

function MenuRow({ icon: Icon, tone, label, description, loading, done, disabled, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="menu-item"
      style={done ? { background: `var(--${tone}-bg)` } : undefined}
    >
      <span
        style={{
          width: 30, height: 30, borderRadius: 'var(--radius-md)', flexShrink: 0,
          background: `var(--${tone}-bg)`, border: `1px solid var(--${tone}-bd)`,
          color: `var(--${tone}-fg)`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}
      >
        {loading ? <Loader2 size={14} className="animate-spin" /> : done ? <Check size={14} /> : <Icon size={14} />}
      </span>
      <span style={{ display: 'block', minWidth: 0 }}>
        <span
          style={{
            display: 'block', fontSize: 13, fontWeight: 600, color: 'var(--text-heading)', lineHeight: 1.2,
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }}
        >
          {label}
          {done && <span style={{ color: 'var(--success-fg)', marginLeft: 6, fontWeight: 400 }}>Téléchargé !</span>}
        </span>
        <span style={{ display: 'block', fontSize: 11, color: 'var(--text-muted)', marginTop: 1 }}>{description}</span>
      </span>
    </button>
  );
}

export default function ExportButton({ content, title, compact = false }) {
  const [open, setOpen] = useState(false);
  const [activeKey, setActiveKey] = useState(null);
  const [success, setSuccess] = useState(null);
  const rootRef = useRef(null);
  const { exportContent, exportFile, exportFilesZip, exporting, exportError } = useExport();

  // Parsing mémoïsé (et mis en cache par contenu dans utils/codeBlocks) : une seule fois par message terminé.
  const files = useMemo(() => exportableFiles(extractFiles(content || '')), [content]);

  useEffect(() => {
    if (!open) return undefined;
    const handler = (e) => {
      if (rootRef.current && !rootRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  const suggestedTitle = title || (content || '').trim().split(/\s+/).slice(0, 6).join(' ');

  const run = async (key, task) => {
    setActiveKey(key);
    try {
      await task();
      setSuccess(key);
      setTimeout(() => { setSuccess(null); setOpen(false); }, 1200);
    } catch {
      /* exportError est déjà positionné par le hook */
    } finally {
      setActiveKey(null);
    }
  };

  const isLoading = exporting && activeKey !== null;

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
            {files.length > 0 && !isLoading && (
              <span style={{ opacity: 0.7 }}>{`(${files.length})`}</span>
            )}
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
            minWidth: 250, maxWidth: 'min(360px, 90vw)', overflow: 'hidden', animation: 'fadeIn 0.18s ease',
          }}
        >
          <div style={{ maxHeight: 'min(60vh, 440px)', overflowY: 'auto' }}>
            {files.length > 0 && (
              <>
                <div className="section-label" style={{ padding: '10px 14px 6px', borderBottom: '1px solid var(--border-subtle)' }}>
                  Détecté dans ce message
                </div>

                {files.map((f) => {
                  const key = `file:${f.id}`;
                  return (
                    <MenuRow
                      key={f.id}
                      icon={FileCode}
                      tone="accent"
                      label={f.filename}
                      description={`${f.lang || 'text'} · ${f.lines} ligne${f.lines > 1 ? 's' : ''}`}
                      loading={activeKey === key}
                      done={success === key}
                      disabled={isLoading}
                      onClick={() => !isLoading && run(key, () => exportFile(f))}
                    />
                  );
                })}

                {files.length > 1 && (
                  <MenuRow
                    icon={FileArchive}
                    tone="info"
                    label="Tout télécharger (.zip)"
                    description={`${files.length} fichiers, arborescence conservée`}
                    loading={activeKey === 'zip'}
                    done={success === 'zip'}
                    disabled={isLoading}
                    onClick={() => !isLoading && run('zip', () => exportFilesZip(files, suggestedTitle))}
                  />
                )}
              </>
            )}

            <div
              className="section-label"
              style={{
                padding: '10px 14px 6px',
                borderBottom: '1px solid var(--border-subtle)',
                borderTop: files.length > 0 ? '1px solid var(--border-subtle)' : undefined,
              }}
            >
              {files.length > 0 ? 'Formats document' : 'Choisir le format'}
            </div>

            {FORMATS.map((fmt) => (
              <MenuRow
                key={fmt.id}
                icon={fmt.icon}
                tone={fmt.tone}
                label={fmt.label}
                description={fmt.description}
                loading={activeKey === fmt.id}
                done={success === fmt.id}
                disabled={isLoading}
                onClick={() => !isLoading && run(fmt.id, () => exportContent(content, fmt.id, suggestedTitle))}
              />
            ))}
          </div>

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
