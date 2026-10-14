/**
 * ExportHistory — tiroir d'historique des exports
 * Usage : <ExportHistory open={show} onClose={() => setShow(false)} />
 */
import { useState, useEffect, useCallback } from 'react';
import { X, Download, Trash2, Globe, FileText, FileSpreadsheet, File, Clock, ChevronRight, AlertCircle } from 'lucide-react';
import { useExport } from '../../hooks/useExport';

const FORMAT_META = {
  html: { icon: Globe, tone: 'warning', label: 'HTML' },
  xlsx: { icon: FileSpreadsheet, tone: 'success', label: 'Excel' },
  docx: { icon: FileText, tone: 'info', label: 'Word' },
  pdf: { icon: File, tone: 'danger', label: 'PDF' },
};

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso) {
  const d = new Date(iso);
  const diff = (new Date() - d) / 1000;
  if (diff < 60) return "À l'instant";
  if (diff < 3600) return `Il y a ${Math.floor(diff / 60)} min`;
  if (diff < 86400) return `Il y a ${Math.floor(diff / 3600)} h`;
  return d.toLocaleDateString('fr-FR', { day: '2-digit', month: 'short', year: 'numeric' });
}

export default function ExportHistory({ open, onClose }) {
  const [history, setHistory] = useState([]);
  const [selected, setSelected] = useState(null);
  const [confirmClear, setConfirmClear] = useState(false);
  const { getHistory, clearHistory } = useExport();

  useEffect(() => {
    if (open) {
      setHistory(getHistory());
      setSelected(null);
    }
  }, [open, getHistory]);

  const handleClear = useCallback(() => {
    if (confirmClear) {
      clearHistory();
      setHistory([]);
      setConfirmClear(false);
    } else {
      setConfirmClear(true);
      setTimeout(() => setConfirmClear(false), 3000);
    }
  }, [confirmClear, clearHistory]);

  if (!open) return null;

  return (
    <>
      <div
        onClick={onClose}
        style={{ position: 'fixed', inset: 0, background: 'var(--overlay)', zIndex: 900, backdropFilter: 'blur(2px)', animation: 'fadeIn 0.2s ease' }}
      />

      <div
        style={{
          position: 'fixed', top: 0, right: 0, bottom: 0, width: 'min(440px, 100vw)',
          background: 'var(--bg-surface)', borderLeft: '1px solid var(--border-subtle)',
          zIndex: 901, display: 'flex', flexDirection: 'column',
          boxShadow: 'var(--shadow-panel)', animation: 'slideInRight 0.22s ease',
        }}
      >
        <div style={{ padding: '18px 20px 14px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <h2 style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-heading)' }}>Historique des exports</h2>
            <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
              {history.length} fichier{history.length !== 1 ? 's' : ''} généré{history.length !== 1 ? 's' : ''}
            </p>
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            {history.length > 0 && (
              <button
                type="button"
                onClick={handleClear}
                className={`btn btn-sm ${confirmClear ? 'btn-danger' : 'btn-ghost'}`}
              >
                <Trash2 size={12} />
                {confirmClear ? 'Confirmer ?' : 'Effacer'}
              </button>
            )}
            <button type="button" onClick={onClose} className="topbar-btn" aria-label="Close">
              <X size={16} />
            </button>
          </div>
        </div>

        <div style={{ flex: 1, overflowY: 'auto' }}>
          {history.length === 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', gap: 12, color: 'var(--text-muted)', padding: 40, textAlign: 'center' }}>
              <Download size={36} strokeWidth={1.5} />
              <div>
                <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 4 }}>Aucun export encore</div>
                <div style={{ fontSize: 12 }}>Exportez un message LLM pour le retrouver ici</div>
              </div>
            </div>
          ) : (
            <div style={{ padding: '8px 0' }}>
              {history.map((entry) => {
                const meta = FORMAT_META[entry.format] || FORMAT_META.html;
                const Icon = meta.icon;
                const isSelected = selected?.id === entry.id;
                const tone = meta.tone;

                return (
                  <div key={entry.id}>
                    <div
                      onClick={() => setSelected(isSelected ? null : entry)}
                      style={{
                        padding: '12px 20px', display: 'flex', alignItems: 'flex-start', gap: 12, cursor: 'pointer',
                        background: isSelected ? `var(--${tone}-bg)` : 'transparent',
                        borderLeft: isSelected ? `3px solid var(--${tone}-fg)` : '3px solid transparent',
                        transition: 'background-color 0.15s',
                      }}
                    >
                      <div
                        style={{
                          width: 36, height: 36, borderRadius: 'var(--radius-md)', flexShrink: 0,
                          background: `var(--${tone}-bg)`, border: `1px solid var(--${tone}-bd)`, color: `var(--${tone}-fg)`,
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                        }}
                      >
                        <Icon size={16} />
                      </div>

                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-heading)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {entry.title || entry.filename}
                        </div>
                        <div style={{ display: 'flex', gap: 8, marginTop: 3, alignItems: 'center' }}>
                          <span className={`badge badge-${tone === 'info' ? 'info' : tone}`} style={{ fontSize: 10 }}>{meta.label}</span>
                          <span style={{ fontSize: 11, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 3 }}>
                            <Clock size={10} />
                            {formatDate(entry.createdAt)}
                          </span>
                          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{formatSize(entry.size)}</span>
                        </div>
                      </div>

                      <ChevronRight
                        size={14}
                        color="var(--text-muted)"
                        style={{ transform: isSelected ? 'rotate(90deg)' : 'none', transition: 'transform 0.2s', flexShrink: 0, marginTop: 2 }}
                      />
                    </div>

                    {isSelected && (
                      <div style={{ margin: '0 20px 8px', borderRadius: 'var(--radius-md)', border: `1px solid var(--${tone}-bd)`, overflow: 'hidden', animation: 'fadeIn 0.2s ease' }}>
                        <div style={{ padding: '10px 14px', background: `var(--${tone}-bg)`, borderBottom: `1px solid var(--${tone}-bd)` }}>
                          <div className="section-label" style={{ color: `var(--${tone}-fg)`, marginBottom: 6 }}>Aperçu du contenu</div>
                          <div style={{ fontSize: 12, color: 'var(--text-primary)', lineHeight: 1.6, maxHeight: 120, overflowY: 'auto', fontFamily: 'var(--font-mono)', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                            {entry.preview}
                            {entry.preview && entry.preview.length >= 300 && <span style={{ color: 'var(--text-muted)' }}> …</span>}
                          </div>
                        </div>
                        <div style={{ padding: '8px 14px', background: 'var(--bg-surface)', display: 'flex', gap: 8, alignItems: 'center' }}>
                          <AlertCircle size={11} color="var(--text-muted)" />
                          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                            Fichier déjà téléchargé — relancez l'export depuis le message pour re-télécharger
                          </span>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div style={{ padding: '12px 20px', borderTop: '1px solid var(--border-subtle)', fontSize: 11, color: 'var(--text-muted)', textAlign: 'center' }}>
          L'historique est stocké localement dans ce navigateur
        </div>
      </div>
    </>
  );
}
