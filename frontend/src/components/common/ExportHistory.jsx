/**
 * ExportHistory.jsx
 * Panneau d'historique des fichiers exportés
 * — Preview du contenu tronqué
 * — Re-téléchargement si le contenu est encore en mémoire (session)
 * — Effacement de l'historique
 *
 * Usage: <ExportHistory open={show} onClose={() => setShow(false)} />
 */

import { useState, useEffect, useCallback } from 'react';
import { X, Download, Trash2, Globe, FileText, FileSpreadsheet, File, Clock, ChevronRight, AlertCircle } from 'lucide-react';
import { useExport } from '../../hooks/useExport';

const FORMAT_META = {
  html:  { icon: Globe,          color: '#e44d26', bg: '#fff3f0', label: 'HTML' },
  xlsx:  { icon: FileSpreadsheet, color: '#1d6f42', bg: '#f0fff4', label: 'Excel' },
  docx:  { icon: FileText,        color: '#2b579a', bg: '#f0f4ff', label: 'Word' },
  pdf:   { icon: File,            color: '#cc0000', bg: '#fff0f0', label: 'PDF'  },
};

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso) {
  const d = new Date(iso);
  const now = new Date();
  const diff = (now - d) / 1000;
  if (diff < 60) return 'À l\'instant';
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
      {/* Overlay */}
      <div
        onClick={onClose}
        style={{
          position: 'fixed', inset: 0,
          background: 'rgba(0,0,0,0.35)',
          zIndex: 900,
          backdropFilter: 'blur(2px)',
          animation: 'fadeIn 0.2s ease'
        }}
      />

      {/* Drawer */}
      <div style={{
        position: 'fixed',
        top: 0, right: 0, bottom: 0,
        width: 'min(440px, 100vw)',
        background: 'white',
        zIndex: 901,
        display: 'flex',
        flexDirection: 'column',
        boxShadow: '-8px 0 40px rgba(0,0,0,0.15)',
        animation: 'slideInRight 0.22s ease'
      }}>
        {/* Header */}
        <div style={{
          padding: '20px 20px 16px',
          borderBottom: '1px solid var(--gray-100)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between'
        }}>
          <div>
            <h2 style={{ fontSize: '16px', fontWeight: '700', color: '#111', margin: 0 }}>
              Historique des exports
            </h2>
            <p style={{ fontSize: '12px', color: 'var(--gray-500)', margin: '2px 0 0' }}>
              {history.length} fichier{history.length !== 1 ? 's' : ''} généré{history.length !== 1 ? 's' : ''}
            </p>
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            {history.length > 0 && (
              <button
                onClick={handleClear}
                style={{
                  display: 'flex', alignItems: 'center', gap: 4,
                  padding: '5px 10px',
                  fontSize: '12px',
                  color: confirmClear ? '#cc0000' : 'var(--gray-500)',
                  background: confirmClear ? '#fff0f0' : 'var(--gray-100)',
                  border: `1px solid ${confirmClear ? '#ffcccc' : 'var(--gray-200)'}`,
                  borderRadius: '6px',
                  cursor: 'pointer',
                  fontWeight: confirmClear ? '600' : '400',
                  transition: 'all 0.2s'
                }}
              >
                <Trash2 size={12} />
                {confirmClear ? 'Confirmer ?' : 'Effacer'}
              </button>
            )}
            <button
              onClick={onClose}
              style={{
                width: 32, height: 32, borderRadius: '8px',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                background: 'var(--gray-100)', border: 'none', cursor: 'pointer'
              }}
            >
              <X size={16} />
            </button>
          </div>
        </div>

        {/* Content */}
        <div style={{ flex: 1, overflowY: 'auto' }}>
          {history.length === 0 ? (
            <div style={{
              display: 'flex', flexDirection: 'column', alignItems: 'center',
              justifyContent: 'center', height: '100%', gap: 12,
              color: 'var(--gray-400)', padding: 40, textAlign: 'center'
            }}>
              <Download size={36} strokeWidth={1.5} />
              <div>
                <div style={{ fontSize: '14px', fontWeight: '600', color: 'var(--gray-500)', marginBottom: 4 }}>
                  Aucun export encore
                </div>
                <div style={{ fontSize: '12px' }}>
                  Exportez un message LLM pour le retrouver ici
                </div>
              </div>
            </div>
          ) : (
            <div style={{ padding: '8px 0' }}>
              {history.map(entry => {
                const meta = FORMAT_META[entry.format] || FORMAT_META.html;
                const Icon = meta.icon;
                const isSelected = selected?.id === entry.id;

                return (
                  <div key={entry.id}>
                    <div
                      onClick={() => setSelected(isSelected ? null : entry)}
                      style={{
                        padding: '12px 20px',
                        display: 'flex',
                        alignItems: 'flex-start',
                        gap: 12,
                        cursor: 'pointer',
                        background: isSelected ? meta.bg : 'white',
                        borderLeft: isSelected ? `3px solid ${meta.color}` : '3px solid transparent',
                        transition: 'all 0.15s'
                      }}
                      onMouseEnter={e => { if (!isSelected) e.currentTarget.style.background = '#fafafa'; }}
                      onMouseLeave={e => { if (!isSelected) e.currentTarget.style.background = 'white'; }}
                    >
                      {/* Format icon */}
                      <div style={{
                        width: 36, height: 36, borderRadius: '9px',
                        background: meta.bg, display: 'flex',
                        alignItems: 'center', justifyContent: 'center', flexShrink: 0
                      }}>
                        <Icon size={16} color={meta.color} />
                      </div>

                      {/* Info */}
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{
                          fontSize: '13px', fontWeight: '600', color: '#111',
                          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'
                        }}>
                          {entry.title || entry.filename}
                        </div>
                        <div style={{ display: 'flex', gap: 8, marginTop: 3, alignItems: 'center' }}>
                          <span style={{
                            fontSize: '10px', fontWeight: '700', letterSpacing: '0.05em',
                            textTransform: 'uppercase', color: meta.color,
                            background: meta.bg, padding: '1px 6px', borderRadius: '4px'
                          }}>
                            {meta.label}
                          </span>
                          <span style={{ fontSize: '11px', color: 'var(--gray-400)', display: 'flex', alignItems: 'center', gap: 3 }}>
                            <Clock size={10} />
                            {formatDate(entry.createdAt)}
                          </span>
                          <span style={{ fontSize: '11px', color: 'var(--gray-400)' }}>
                            {formatSize(entry.size)}
                          </span>
                        </div>
                      </div>

                      <ChevronRight
                        size={14}
                        color="var(--gray-300)"
                        style={{ transform: isSelected ? 'rotate(90deg)' : 'rotate(0)', transition: 'transform 0.2s', flexShrink: 0, marginTop: 2 }}
                      />
                    </div>

                    {/* Preview accordéon */}
                    {isSelected && (
                      <div style={{
                        margin: '0 20px 8px',
                        borderRadius: '8px',
                        border: `1px solid ${meta.color}30`,
                        overflow: 'hidden',
                        animation: 'expandDown 0.2s ease'
                      }}>
                        <div style={{
                          padding: '10px 14px',
                          background: meta.bg,
                          borderBottom: `1px solid ${meta.color}20`
                        }}>
                          <div style={{ fontSize: '11px', fontWeight: '700', color: meta.color, letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 6 }}>
                            Aperçu du contenu
                          </div>
                          <div style={{
                            fontSize: '12px', color: '#444', lineHeight: 1.6,
                            maxHeight: 120, overflowY: 'auto',
                            fontFamily: "'Menlo', 'Consolas', monospace",
                            whiteSpace: 'pre-wrap', wordBreak: 'break-word'
                          }}>
                            {entry.preview}
                            {entry.preview && entry.preview.length >= 300 && (
                              <span style={{ color: 'var(--gray-400)' }}> …</span>
                            )}
                          </div>
                        </div>

                        <div style={{ padding: '8px 14px', background: 'white', display: 'flex', gap: 8, alignItems: 'center' }}>
                          <AlertCircle size={11} color="var(--gray-400)" />
                          <span style={{ fontSize: '11px', color: 'var(--gray-400)' }}>
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

        {/* Footer */}
        <div style={{
          padding: '12px 20px',
          borderTop: '1px solid var(--gray-100)',
          fontSize: '11px', color: 'var(--gray-400)', textAlign: 'center'
        }}>
          L'historique est stocké localement dans ce navigateur
        </div>
      </div>

      <style>{`
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        @keyframes slideInRight {
          from { transform: translateX(100%); opacity: 0; }
          to   { transform: translateX(0); opacity: 1; }
        }
        @keyframes expandDown {
          from { opacity: 0; transform: translateY(-6px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </>
  );
}